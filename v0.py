from ursina import (
    Ursina, Entity, Sky, DirectionalLight, AmbientLight, Vec3, Vec2, color,
    Text, window, application, raycast, clamp, invoke, destroy, held_keys, lerp, camera, curve,
    Button, Audio  # Added missing imports
)
from ursina.shaders import lit_with_shadows_shader
import math

# --- Helper Functions ---
def distance_xz(a, b):
    return math.sqrt((a.x - b.x)**2 + (a.z - b.z)**2)

def distance_sq(a, b):
    return (a.x - b.x)**2 + (a.y - b.y)**2 + (a.z - b.z)**2

# --- Engine Core ---
class HedgehogEngine:
    def __init__(self):
        self.app = Ursina(vsync=True)
        application.target_fps = 60
        window.title = 'Hedgehog Engine - Pure Vibes Demo'
        window.borderless = False
        window.fullscreen = False
        window.exit_button.visible = False
        window.fps_counter.enabled = True

        # Engine Systems
        self.rendering_system = RenderingSystem()
        self.level_system = LevelSystem(self.rendering_system)
        self.input_system = InputSystem()
        self.physics_system = PhysicsSystem(self.level_system, None)  # AudioSystem is optional
        self.camera_system = CameraSystem()
        self.audio_system = AudioSystem()
        self.main_menu_system = MainMenuSystem(self)

        # Game State
        self.game_started = False
        self.player = None
        self.collected_rings = 0

        self.main_menu_system.show_menu()
        self.app.run()

    def start_game_from_menu(self):
        if not self.game_started:
            self.setup_game_once()
            self.game_started = True
        else:
            self.reset_game_state()
        self.main_menu_system.hide_menu()
        if self.player:
            self.player.enable()
            self.player.position = (0, 2, -5)
            self.player.velocity = Vec3(0, 0, 0)
            self.player.speed = 0
            self.player.is_homing = False

    def reset_game_state(self):
        rings_to_destroy = list(self.level_system.rings)
        for r in rings_to_destroy:
            if r in self.level_system.targetable_entities:
                self.level_system.targetable_entities.remove(r)
            destroy(r)
        self.level_system.rings.clear()

        springs_to_destroy = list(self.level_system.springs)
        for s in springs_to_destroy:
            destroy(s)
        self.level_system.springs.clear()

        self.level_system.generate_test_level_dynamic_elements()
        self.collected_rings = 0
        if self.player:
            self.player.position = (0, 2, -5)
            self.player.velocity = Vec3(0, 0, 0)
            self.player.speed = 0
            self.player.is_homing = False
            self.player.is_grounded = False
            self.player.can_double_jump = True

    def setup_game_once(self):
        self.rendering_system.setup_environment()
        self.level_system.generate_test_level()
        self.player = PlayerCharacter(position=(0, 2, -5), shader=self.rendering_system.default_shader)
        self.camera_system.setup(self.player)
        self.physics_system.set_player(self.player)
        self.rendering_system.setup_debug_text()
        self.app.update = self.update

    def update(self):
        dt = application.time_step
        if dt > 1 / 30:
            dt = 1 / 30
        if self.main_menu_system.menu_active:
            return

        self.input_system.update()
        interaction_results = self.physics_system.update(self.input_system.move_direction, held_keys['space'], dt)

        if interaction_results.get('rings_collected', 0) > 0:
            self.collected_rings += interaction_results['rings_collected']
            self.audio_system.play('ring')
        if interaction_results.get('hit_spring'):
            self.audio_system.play('spring')
        if interaction_results.get('jumped'):
            self.audio_system.play('jump')
        if interaction_results.get('homing_started'):
            self.audio_system.play('homing')

        if self.player:
            self.player.update_animation(dt)
            self.camera_system.update(dt)
            if self.rendering_system.debug_text and self.rendering_system.debug_text.enabled:
                self.rendering_system.update_debug_info(self.player, self.collected_rings, dt)

        if held_keys['escape'] and not self.main_menu_system.menu_active:
            self.main_menu_system.show_menu()

# --- Rendering System ---
class RenderingSystem:
    def __init__(self):
        self.default_shader = lit_with_shadows_shader
        self.debug_text = None

    def setup_debug_text(self):
        if not self.debug_text:
            self.debug_text = Text(
                text="", 
                position=window.top_left + Vec2(0.01, -0.01),
                origin=(-0.5, 0.5),
                scale=1.2,
                color=color.azure,
                enabled=False
            )

    def setup_environment(self):
        Sky(color=color.rgb(100, 150, 255))
        sun = DirectionalLight(color=color.rgb(255, 255, 230), direction=(0.5, -1, 0.8), shadows=True)
        sun.look_at(Vec3(0, -1, 0))
        AmbientLight(color=color.rgba(100, 100, 120, 0.3))

    def update_debug_info(self, player, rings, dt):
        if not self.debug_text or not player:
            return
        self.debug_text.text = (
            f"Speed: {player.speed:.1f}\n"
            f"Velocity Y: {player.velocity.y:.1f}\n"
            f"Grounded: {player.is_grounded}\n"
            f"Homing: {player.is_homing}\n"
            f"Rings: {rings}\n"
            f"FPS: {round(1/dt) if dt > 0 else 'inf'}"
        )

# --- Level System (Truncated for Brevity) ---
class LevelSystem:
    def __init__(self, rendering_system):
        self.entities = []
        self.rings = []
        self.springs = []
        self.targetable_entities = []
        self.renderer = rendering_system

    def generate_test_level(self):
        self._add_entity(model='plane', scale=(150, 1, 150), color=color.green, collider='box')
        self._make_platform((0, 0.5, 0), (20, 1, 10), color.gray)
        self._make_ring_line((0, 3, 5), (0, 3, 25), 8)
        self._make_spring((5, 1, 35), power=25)

    def _add_entity(self, **kwargs):
        if 'shader' not in kwargs:
            kwargs['shader'] = self.renderer.default_shader
        e = Entity(**kwargs)
        self.entities.append(e)
        return e

    def _make_platform(self, pos, scale, col):
        return self._add_entity(model='cube', position=pos, scale=scale, color=col, collider='box')

    def _make_ring(self, pos):
        ring = self._add_entity(model='torus', color=color.gold, scale=1.0, position=pos, rotation=(90, 0, 0), collider='sphere', tag='ring')
        self.rings.append(ring)
        self.targetable_entities.append(ring)
        return ring

    def _make_ring_line(self, start, end, count):
        start_vec = Vec3(start)
        end_vec = Vec3(end)
        step = (end_vec - start_vec) / (count - 1)
        for i in range(count):
            self._make_ring(start_vec + step * i)

    def _make_spring(self, pos, power):
        spring = self._add_entity(model='cylinder', color=color.orange, scale=(1, 0.4, 1), position=pos, collider='box', tag='spring', power=power)
        self.springs.append(spring)
        return spring

    def remove_targetable(self, entity):
        if entity in self.targetable_entities:
            self.targetable_entities.remove(entity)

# --- Input System ---
class InputSystem:
    def __init__(self):
        self.move_direction = Vec3(0, 0, 0)
        self.jump_pressed = False

    def update(self):
        self.move_direction = Vec3(
            held_keys['d'] - held_keys['a'],
            0,
            held_keys['w'] - held_keys['s']
        ).normalized()
        self.jump_pressed = held_keys['space']

# --- Physics System ---
class PhysicsSystem:
    def __init__(self, level_system, audio_system):
        self.player = None
        self.level = level_system
        self.audio_system = audio_system
        self.gravity = 35
        self.homing_range_sq = 225

    def set_player(self, player):
        self.player = player

    def update(self, input_dir, jump, dt):
        p = self.player
        if not p:
            return {'rings_collected': 0, 'hit_spring': False, 'jumped': False, 'homing_started': False}

        # Simplified physics logic here (see full file for complete implementation)
        return {'rings_collected': 0}

    def _find_homing_target(self):
        return None

# --- Camera System ---
class CameraSystem:
    def __init__(self):
        camera.fov = 75
        self.target = None

    def setup(self, target):
        self.target = target

    def update(self, dt):
        if not self.target:
            return
        p = self.target
        cam_dist = lerp(9, 15, clamp(p.speed / 25, 0, 1))
        cam_height = lerp(2.5, 4.5, clamp(p.speed / 25, 0, 1))
        target_cam_pos = p.world_position - (p.forward * cam_dist) + Vec3(0, cam_height, 0)
        camera.position = lerp(camera.position, target_cam_pos, dt * 7)
        camera.look_at(p.world_position + Vec3(0, p.scale_y * 0.3, 0))

# --- Audio System ---
class AudioSystem:
    def __init__(self):
        self.sounds = {
            'jump': Audio('assets/jump.wav', loop=False, autoplay=False),
            'ring': Audio('assets/ring.wav', loop=False, autoplay=False),
            'spring': Audio('assets/spring.wav', loop=False, autoplay=False),
            'homing': Audio('assets/homing.wav', loop=False, autoplay=False),
        }

    def play(self, sound_name, volume=1.0):
        sound = self.sounds.get(sound_name)
        if sound:
            sound.volume = volume
            sound.play()

# --- Player Character ---
class PlayerCharacter(Entity):
    def __init__(self, **kwargs):
        super().__init__(model='sphere', color=color.blue, scale=1.0, collider='sphere', **kwargs)
        self.speed = 0
        self.velocity = Vec3(0, 0, 0)
        self.max_speed = 25
        self.jump_power = 13
        self.is_grounded = False
        self.is_homing = False
        self.quills = Entity(parent=self, model='cone', color=color.blue.tint(-0.2), scale=(0.6, 1.5, 0.6), position=(0, 0.3, -0.3))

    def update_animation(self, dt):
        pass

# --- Main Menu System ---
class MainMenuSystem:
    def __init__(self, engine):
        self.engine = engine
        self.menu_active = False
        self.title_text = Text(text='Hedgehog Engine CD', origin=(0, -7), scale=3.5, color=color.cyan, enabled=False, font='arial.ttf')
        self.buttons = [
            Button(text='Start Game', on_click=self.engine.start_game_from_menu),
            Button(text='Quit', on_click=application.quit)
        ]

    def show_menu(self):
        self.menu_active = True
        self.title_text.enable()
        for b in self.buttons:
            b.enable()

    def hide_menu(self):
        self.menu_active = False
        self.title_text.disable()
        for b in self.buttons:
            b.disable()

# --- Run the Engine ---
if __name__ == '__main__':
    engine = HedgehogEngine()
