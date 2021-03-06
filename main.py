import os
import sys

from direct.showbase.ShowBase import ShowBase
from direct.showbase.Audio3DManager import Audio3DManager

import panda3d

import pman.shim

from panda3d.core import NodePath
from panda3d.bullet import BulletDebugNode

from environment import Environment
from vehicle import Vehicle
from keybindings import DeviceListener
from camera import CameraController
from controller import VehicleController


panda3d.core.load_prc_file(
    panda3d.core.Filename.expand_from('$MAIN_DIR/settings.prc')
)


class GameApp(ShowBase):
    def __init__(self, map="lab"):
        ShowBase.__init__(self)
        pman.shim.init(self)

        self.audio3d = Audio3DManager(
            base.sfxManagerList[0],
            base.cam,
        )

        self.accept('escape', sys.exit)
        #self.render.setShaderAuto()
        self.set_frame_rate_meter(True)
        self.accept('f12', self.debug)

        self.environment = Environment(self, map)
        self.bullet_debug()
        self.accept("f1", self.toggle_bullet_debug)

        self.vehicles = []
        vehicle_files = [
            'Ricardeaut_Magnesium',
            'Ricardeaut_Himony',
            #'Psyoni_Culture',
            #'Texopec_Nako',
            #'Texopec_Reaal',
            # 'Doby_Phalix',
        ]

        for vehicle_file in vehicle_files:
            vehicle = Vehicle(
                self,
                vehicle_file,
            )
            self.vehicles.append(vehicle)

        spawn_points = self.environment.get_spawn_points()
        for vehicle, spawn_point in zip(self.vehicles, spawn_points):
            vehicle.place(spawn_point)

        self.controller_listener = DeviceListener()

        self.player_vehicle_idx = 0
        self.player_controller = VehicleController(
            self,
            self.vehicles[self.player_vehicle_idx],
            self.controller_listener,
        )
        self.player_camera = CameraController(
            base.cam,
            self.vehicles[self.player_vehicle_idx],
            self.player_controller,
        )

        base.task_mgr.add(
            self.game_loop_pre_render,
            "game_loop_pre_render",
            sort=45,
        )
        base.task_mgr.add(
            self.game_loop_post_render,
            "game_loop_post_render",
            sort=55,
        )

    def game_loop_pre_render(self, task):
        self.player_controller.gather_inputs()
        for vehicle in self.vehicles:
            vehicle.game_loop()
        self.player_camera.update()
        return task.cont

    def game_loop_post_render(self, task):
        self.environment.update_physics()
        return task.cont

    def next_vehicle(self):
        num_vehicles = len(self.vehicles)
        self.player_vehicle_idx = (self.player_vehicle_idx + 1) % num_vehicles
        new_vehicle = self.vehicles[self.player_vehicle_idx]
        self.player_camera.set_vehicle(new_vehicle)
        self.player_controller.set_vehicle(new_vehicle)

    def bullet_debug(self):
        debug_node = BulletDebugNode('Debug')
        debug_node.show_wireframe(True)
        debug_node.show_constraints(True)
        debug_node.show_bounding_boxes(False)
        debug_node.show_normals(False)
        self.debug_np = self.render.attach_new_node(debug_node)
        self.environment.physics_world.set_debug_node(debug_node)

    def toggle_bullet_debug(self):
        if self.debug_np.is_hidden():
            self.debug_np.show()
        else:
            self.debug_np.hide()

    def debug(self):
        import pdb
        pdb.set_trace()


def main():
    if len(sys.argv) > 1:
        map = sys.argv[1]
        app = GameApp(map)
    else:
        app = GameApp()
    app.run()


if __name__ == '__main__':
    main()
