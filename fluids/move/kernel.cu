#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include "math_functions.h"
#include "cudart_platform.h"

#include <algorithm>
#include <iostream>
#include <cstdlib>

using uint8_t = unsigned char;

struct vec2
{
	float x = 0.0, y = 0.0;

	__device__ vec2 operator-(vec2 other)
	{
		vec2 res;
		res.x = this->x - other.x;
		res.y = this->y - other.y;
		return res;
	}

	__device__ vec2 operator+(vec2 other)
	{
		vec2 res;
		res.x = this->x + other.x;
		res.y = this->y + other.y;
		return res;
	}

	__device__ vec2 operator*(float d)
	{
		vec2 res;
		res.x = this->x * d;
		res.y = this->y * d;
		return res;
	}
};

struct Particle
{
	vec2 u; // velocity
	float q; // quantity
	float intensityR = 1.0f;
	float intensityG = 0.2f;
	float intensityB = 1.0f;
};

static Particle* cpuField;
static Particle* newField;
static Particle* oldField;
static uint8_t* colorField;
static size_t xSize, ySize;
static float* pressureOld;
static float* pressureNew;

// interpolates quantity of grid cells
__device__ vec2 interpolate(vec2 v, Particle* field, size_t xSize, size_t ySize)
{
	float x1 = (int)v.x;
	float y1 = (int)v.y;
	float x2 = (int)v.x + 1;
	float y2 = (int)v.y + 1;
	vec2 q1, q2, q3, q4;
	#define SET(Q, x, y) if (x < xSize && x >= 0 && y < ySize && y >= 0) Q = field[int(y) * xSize + int(x)].u
	SET(q1, x1, y1);
	SET(q2, x1, y2);
	SET(q3, x2, y1);
	SET(q4, x2, y2);
	#undef SET
	vec2 f1 = q1 * ((x2 - v.x) / (x2 - x1)) + q3 * ((v.x - x1) / (x2 - x1));
	vec2 f2 = q2 * ((x2 - v.x) / (x2 - x1)) + q4 * ((v.x - x1) / (x2 - x1));
	return f1 * ((y2 - v.y) / (y2 - y1)) + f2 * ((v.y - y1) / (y2 - y1));
}

// performs iteration of jacobi method on grid field
__device__ vec2 jacobiVelocity(Particle* field, size_t xSize, size_t ySize, vec2 v, vec2 B, float alpha, float beta)
{
	vec2 vU, vD, vR, vL; 	     
	#define SET(U, x, y) if (x < xSize && x >= 0 && y < ySize && y >= 0) U = field[int(y) * xSize + int(x)].u
	SET(vU, v.x, v.y - 1);
	SET(vD, v.x, v.y + 1);
	SET(vL, v.x - 1, v.y);
	SET(vR, v.x + 1, v.y);
	#undef SET
	v = (vU + vD + vL + vR + B * alpha) * (1.0f / beta);
	return v;
}

__device__ float jacobiPressure(float* pressureField, size_t xSize, size_t ySize, int x, int y, float B, float alpha, float beta)
{
	float xU = 0.0f, xD = 0.0f, xL = 0.0f, xR = 0.0f;
	#define SET(P, x, y) if (x < xSize && x >= 0 && y < ySize && y >= 0) P = pressureField[int(y) * xSize + int(x)]
	SET(xU, x, y - 1);
	SET(xD, x, y + 1);
	SET(xL, x - 1, y);
	SET(xR, x + 1, y);
	#undef SET
	float pressure = (xU + xD + xL + xR + alpha * B) * (1.0f / beta);
	return pressure;
}

__device__ float divergency(Particle* field, size_t xSize, size_t ySize, int x, int y)
{
	float x1 = 0.0f, x2 = 0.0f, y1 = 0.0f, y2 = 0.0f;
	#define SET(P, x, y) if (x < xSize && x >= 0 && y < ySize && y >= 0) P = field[int(y) * xSize + int(x)]
	SET(x1, x + 1, y).u.x;
	SET(x2, x - 1, y).u.x;
	SET(y1, x, y + 1).u.y;
	SET(y2, x, y - 1).u.y;
	#undef SET
	return (x1 - x2) / 2 + (y1 - y2) / 2;
}

__device__ vec2 gradient(float* pField, size_t xSize, size_t ySize, int x, int y)
{
	#define SET(P, x, y) if (x < xSize && x >= 0 && y < ySize && y >= 0) P = pField[int(y) * xSize + int(x)]
	float x1 = 0.0f, x2 = 0.0f, y1 = 0.0f, y2 = 0.0f;
	SET(x1, x + 1, y);
	SET(x2, x - 1, y);
	SET(y1, x, y + 1);
	SET(y2, x, y - 1);
	#undef SET
	vec2 res = { (x1 - x2) / 2.0f, (y1 - y2) / 2.0f };
	return res;	 
}

__device__ float sigm(float x)
{
	return 1.0f / (1.0f + powf(1.2f, -x));
}

// adds quantity to particles using bilinear interpolation
__global__ void advect(Particle* newField, Particle* oldField, size_t xSize, size_t ySize, float dt)
{
	int x = blockIdx.x * blockDim.x + threadIdx.x;
	int y = blockIdx.y * blockDim.y + threadIdx.y;
	vec2 pos = { x * 1.0f, y * 1.0f };
	Particle& Pnew = newField[y * xSize + x];
	Particle& Pold = oldField[y * xSize + x];
	// find new quantity tracing where it came from
	Pnew.u = interpolate(pos - Pold.u * dt, oldField, xSize, ySize);
}

__global__ void paint(uint8_t* colorField, Particle* field, size_t xSize, size_t ySize)
{
	int x = blockIdx.x * blockDim.x + threadIdx.x;
	int y = blockIdx.y * blockDim.y + threadIdx.y;
	float q = (sigm(sqrt(powf(field[y * xSize + x].u.x, 2) + powf(field[y * xSize + x].u.y, 2))) - 0.5) * 2;
	float R = field[y * xSize + x].intensityR;
	float G = field[y * xSize + x].intensityG;
	float B = field[y * xSize + x].intensityB;
	colorField[4 * (y * xSize + x) + 0] = 255 * powf(q, 4.0f);
	colorField[4 * (y * xSize + x) + 1] = 255 * powf(q, 0.4f);
	colorField[4 * (y * xSize + x) + 2] = 255 * powf(q, 4.0f);
	colorField[4 * (y * xSize + x) + 3] = 255;
}

// calculates nonzero divergency velocity field u
__global__ void diffuse(Particle* newField, Particle* oldField, size_t xSize, size_t ySize, float viscosity, float dt)
{
	int x = blockIdx.x * blockDim.x + threadIdx.x;
	int y = blockIdx.y * blockDim.y + threadIdx.y;
	vec2 pos = { x * 1.0f, y * 1.0f };
	vec2 u = oldField[y * xSize + x].u;
	// perfom one iteration of jacobi method (diffuse method should be called 20-50 times per cell)
	float alpha = viscosity * viscosity / dt;
	float beta = 4.0f + alpha;
	newField[y * xSize + x].u = jacobiVelocity(oldField, xSize, ySize, pos, u, alpha, beta);
}

__global__ void computePressure(Particle* newField, size_t xSize, size_t ySize, float* pNew, float* pOld, float density, float dt)
{
	int x = blockIdx.x * blockDim.x + threadIdx.x;
	int y = blockIdx.y * blockDim.y + threadIdx.y;
	float div = divergency(newField, xSize, ySize, x, y);
	float alpha = -1.0f * density * density;
	float beta = 4.0;
	pNew[y * xSize + x] = jacobiPressure(pOld, xSize, ySize, x, y, div, alpha, beta);
}

__global__ void project(Particle* newField, size_t xSize, size_t ySize, float* pField)
{
	int x = blockIdx.x * blockDim.x + threadIdx.x;
	int y = blockIdx.y * blockDim.y + threadIdx.y;
	vec2& u = newField[y * xSize + x].u;
	u = u - gradient(pField, xSize, ySize, x, y);
}

float randomf()
{
	return rand() * 1.0f / RAND_MAX;
}

void applyForce(int x1, int y1, int x2, int y2, int r, float R, float G, float B)
{
	cudaMemcpy(cpuField, oldField, xSize * ySize * sizeof(Particle), cudaMemcpyDeviceToHost);
	float color = randomf();
	float length = std::sqrtf(powf(x2 - x1, 2) + powf(y2 - y1, 2)) + 1;
	for (int dx = -r; dx < r; dx++)
	{
		for (int dy = -r; dy < r; dy++)
		{
			if (dx * dx + dy * dy < r * r)
			{
				int ax = std::max(0, std::min(int(xSize) - 1, x1 + dx));
				int ay = std::max(0, std::min(int(ySize) - 1, y1 + dy));
				vec2& u = cpuField[ay * xSize + ax].u;
				u.x += (x2 - x1) * 100 / length;
				//u.x = randomf() * 10;
				u.y += (y2 - y1) * 100 / length;
				
				//u.x = randomf() * 10.0f;
				//u.y = randomf() * 10.0f;
				cpuField[ay * xSize + ax].q = color;
				/*
				cpuField[ay * xSize + ax].intensityR = R;
				cpuField[ay * xSize + ax].intensityG = G;
				cpuField[ay * xSize + ax].intensityB = B;
				*/
			}
		}
	}
	cudaMemcpy(oldField, cpuField, xSize * ySize * sizeof(Particle), cudaMemcpyHostToDevice);
}

void cudaInit(size_t x, size_t y)
{
	xSize = x, ySize = y;
	cudaSetDevice(0);
	size_t size = xSize * ySize * 4 * sizeof(uint8_t);
	cudaMalloc(&colorField, size);
	cudaMalloc(&oldField, xSize * ySize * sizeof(Particle));
	cudaMalloc(&newField, xSize * ySize * sizeof(Particle));
	cudaMalloc(&pressureOld, xSize * ySize * sizeof(float));
	cudaMalloc(&pressureNew, xSize * ySize * sizeof(float));

	cudaMemset(oldField, 0, xSize * ySize * sizeof(Particle));
	cudaMemset(pressureOld, 0, xSize * ySize * sizeof(float));

	cpuField = new Particle[xSize * ySize];
}

void cudaExit()
{
	delete[] cpuField;
	cudaFree(colorField);
	cudaFree(oldField);
	cudaFree(newField);
	cudaFree(pressureOld);
	cudaFree(pressureNew);
	cudaDeviceReset();
}

void computeField(uint8_t* result, float dt, float viscosity, float density)
{
	int iterations = 50;
	dim3 threadsPerBlock(20, 20);
	dim3 numBlocks(xSize / threadsPerBlock.x, ySize / threadsPerBlock.y);
	// run advect -> diffuse -> force -> project
	advect<<<numBlocks, threadsPerBlock>>>(newField, oldField, xSize, ySize, dt);
	cudaDeviceSynchronize();
	std::swap(newField, oldField);

#if 0
	Particle* tmp = new Particle[xSize * ySize];
	cudaMemcpy(tmp, newField, xSize * ySize * sizeof(Particle), cudaMemcpyDeviceToHost);
	printf("%f ", tmp[100 * ySize + 100].q);
	std::cout << '[' << tmp[100 * ySize + 100].u.x << ' ';
	std::cout		 << tmp[100 * ySize + 100].u.y << "]\n";
	delete[] tmp;
#endif
	
	paint<<<numBlocks, threadsPerBlock>>>(colorField, newField, xSize, ySize);
	cudaDeviceSynchronize();
	for (int i = 0; i < iterations; i++)
	{
		diffuse<<<numBlocks, threadsPerBlock>>>(newField, oldField, xSize, ySize, viscosity, dt);
		cudaDeviceSynchronize();
		std::swap(newField, oldField);
	}
	for (int i = 0; i < iterations; i++)
	{
		computePressure<<<numBlocks, threadsPerBlock>>>(newField, xSize, ySize, pressureNew, pressureOld, density, dt);
		cudaDeviceSynchronize();
		std::swap(pressureNew, pressureOld);
	}
	project<<<numBlocks, threadsPerBlock>>>(newField, xSize, ySize, pressureOld);
	cudaDeviceSynchronize();
	cudaMemset(pressureOld, 0, xSize * ySize * sizeof(float));

	size_t size = xSize * ySize * 4 * sizeof(uint8_t);
	cudaMemcpy(result, colorField, size, cudaMemcpyDeviceToHost);
	cudaError_t error = cudaGetLastError();
	if (error != cudaSuccess)
	{
		std::cout << cudaGetErrorName(error) << std::endl;
	}
}