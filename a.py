from ursina import *

app = Ursina()

# Player entity
player = Entity(model='cube', color=color.red, scale=1, position=(0, 0, 0))

# Camera setup
camera.position = (0, 10, -20)
camera.look_at(player)

# UI element - Start button near the top center
start_button = Button(text='Start Game', scale=0.1, position=(0, 0.9))
def start_game():
    print("Game started!")
start_button.on_click = start_game

# Ground for reference
ground = Entity(model='plane', scale=(10, 1, 10), color=color.green, position=(0, -1, 0))

def update():
    # Basic WASD movement
    speed = 5 * time.dt
    if held_keys['w']:
        player.z += speed
    if held_keys['s']:
        player.z -= speed
    if held_keys['a']:
        player.x -= speed
    if held_keys['d']:
        player.x += speed

app.run()
