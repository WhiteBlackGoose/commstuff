#include <SFML/Graphics.hpp>
#include <vector>
#include <cstdlib>
#include <cmath>
#include <iostream>
#include <algorithm>
#include <functional>
#include <limits>
#include <chrono>
#include <iomanip>

using namespace std;

//SFML REQUIRED TO LAUNCH THIS CODE

#define WINDOW_WIDTH 1280
#define WINDOW_HEIGHT 720

#define VISCOSITY 1.0f
#define DENSITY 1.0f

float random()
{
	return rand() / float(RAND_MAX);
}

void computeField(uint8_t* result, float dt, float viscosity, float density);
void applyForce(int x1, int y1, int x2, int y2, int r, float R, float G, float B);
void cudaInit(size_t xSize, size_t ySize);
void cudaExit();

int main()
{
	cudaInit(WINDOW_WIDTH, WINDOW_HEIGHT);
	srand(time(NULL));
	sf::RenderWindow window(sf::VideoMode(WINDOW_WIDTH, WINDOW_HEIGHT), "demo");

	auto start = chrono::system_clock::now();
	auto end = chrono::system_clock::now();

	sf::Image frame;
	sf::Texture texture;
	sf::Sprite sprite;
	sf::Uint8* pixels = new sf::Uint8[WINDOW_HEIGHT * WINDOW_WIDTH * 4];

	sf::Vector2i mousePos;

	bool down = false;
	bool frozen = false;
	while (window.isOpen())
	{
		end = chrono::system_clock::now();
		chrono::duration<float> diff = end - start;
		window.setTitle(std::to_string(int(1.0f / diff.count())) + " fps");
		start = end;
		window.clear(sf::Color::White);
		sf::Event event;
		float r = 0;
		while (window.pollEvent(event))
		{
			if (event.type == sf::Event::Closed)
				window.close();
			
			if (event.type == sf::Event::MouseButtonPressed)
			{
				if (event.mouseButton.button == sf::Mouse::Button::Left)
				{
					mousePos = { event.mouseButton.x, event.mouseButton.y };
					down = true;
					r = random();
				}
				else
					frozen = !frozen;
			}
			if (event.type == sf::Event::MouseButtonReleased)
			{
				down = false;
				//applyForce(mousePos.x, mousePos.y, event.mouseButton.x, event.mouseButton.y, 15);
			}
			if (event.type == sf::Event::MouseMoved && down)
			{
				//cout << event.mouseMove.x << " " << event.mouseMove.y << endl;
				
				if(r < 0.3)
					applyForce(mousePos.x, mousePos.y, event.mouseMove.x, event.mouseMove.y, 20, 0.25, 2.5, 0.25);
				else if(r < 0.6)
					applyForce(mousePos.x, mousePos.y, event.mouseMove.x, event.mouseMove.y, 20, 1.0, 0.1, 1.0);
				else
					applyForce(mousePos.x, mousePos.y, event.mouseMove.x, event.mouseMove.y, 20, 0.5, 0.5, 0.5);
				mousePos = { event.mouseMove.x, event.mouseMove.y };
			}
		}
		float dt = diff.count();
		if(!frozen)
			computeField(pixels, dt, VISCOSITY, DENSITY);

		frame.create(WINDOW_WIDTH, WINDOW_HEIGHT, pixels);
		texture.loadFromImage(frame);
		sprite.setTexture(texture);
		window.draw(sprite);
		window.display();
	}
	cudaExit();
	delete[] pixels;
	return 0;
}
