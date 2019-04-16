import os
import sys
from math import cos, pi
from random import random

from direct.showbase.ShowBase import ShowBase
import panda3d
import pman.shim

from panda3d.core import NodePath
from panda3d.core import Vec3
from panda3d.core import VBase4
from panda3d.core import Plane
from panda3d.core import DirectionalLight
from panda3d.core import CollisionTraverser
from panda3d.core import CollisionHandlerQueue
from panda3d.core import CollisionNode
from panda3d.core import CollisionRay
from panda3d.core import CollisionPlane
from panda3d.bullet import BulletWorld
from panda3d.bullet import BulletRigidBodyNode
from panda3d.bullet import BulletBoxShape
from panda3d.bullet import BulletTriangleMesh
from panda3d.bullet import BulletTriangleMeshShape
from panda3d.bullet import BulletPlaneShape
from panda3d.bullet import BulletDebugNode

panda3d.core.load_prc_file(
    panda3d.core.Filename.expand_from('$MAIN_DIR/settings.prc')
)


class GameApp(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        pman.shim.init(self)
        self.accept('escape', sys.exit)

        self.physics_world = BulletWorld()
        self.physics_world.setGravity(Vec3(0, 0, -9.81))
        self.bullet_debug()

        self.repulsor_traverser = CollisionTraverser('repulsor')
        #self.repulsor_traverser.show_collisions(base.render)

        environment = Environment(self, "assets/maps/plane.bam")
        spawn_points = environment.get_spawn_points()

        self.vehicles = []
        vehicle_1 = Vehicle(self, "assets/cars/Ricardeaut_Magnesium.bam")
        self.vehicles.append(vehicle_1)
        vehicle_2 = Vehicle(self, "assets/cars/Ricardeaut_Magnesium.bam")
        self.vehicles.append(vehicle_2)



        for vehicle, spawn_point in zip(self.vehicles, spawn_points):
            vehicle.place(
                spawn_point.get_pos() + Vec3(0, 0, 0.5),
                spawn_point.get_hpr(),
            )

        self.player_vehicle_idx = 0
        self.player_camera = CameraController(
            self,
            base.cam,
            self.vehicles[self.player_vehicle_idx],
        )


        self.player_controller = VehicleController(
            self,
            self.vehicles[self.player_vehicle_idx],
        )

        base.task_mgr.add(self.run_repulsors, 'run repulsors', sort=0)
        base.task_mgr.add(self.run_gyroscopes, 'run gyroscopes', sort=1)
        base.task_mgr.add(self.update_physics, 'physics', sort=2)
        base.task_mgr.add(self.player_camera.update, "camera", sort=3)

    def next_vehicle(self):
        self.player_vehicle_idx = (self.player_vehicle_idx + 1) % len(self.vehicles)
        self.player_camera.set_vehicle(self.vehicles[self.player_vehicle_idx])
        self.player_controller.set_vehicle(self.vehicles[self.player_vehicle_idx])

    def run_repulsors(self, task):
        self.repulsor_traverser.traverse(base.render)
        for vehicle in self.vehicles:
            vehicle.apply_repulsors()
        return task.cont

    def run_gyroscopes(self, task):
        for vehicle in self.vehicles:
            vehicle.apply_gyroscope()
        return task.cont

    def update_physics(self, task):
        dt = globalClock.getDt()
        self.physics_world.doPhysics(dt)
        return task.cont

    def bullet_debug(self):
        debugNode = BulletDebugNode('Debug')
        debugNode.showWireframe(True)
        debugNode.showConstraints(True)
        debugNode.showBoundingBoxes(False)
        debugNode.showNormals(False)
        debugNP = self.render.attachNewNode(debugNode)
        debugNP.show()

        self.physics_world.setDebugNode(debugNP.node())


class Environment:
    def __init__(self, app, map_file):
        self.app = app

        shape = BulletPlaneShape(Vec3(0, 0, 1), 0)
        node = BulletRigidBodyNode('Ground')
        node.addShape(shape)
        self.np = self.app.render.attach_new_node(node)
        self.np.setPos(0, 0, 0)
        self.app.physics_world.attachRigidBody(node)

        model = loader.load_model(map_file)
        model.reparent_to(self.np)

        coll_solid = CollisionPlane(Plane((0, 0, 1), (0, 0, 0)))
        coll_node = CollisionNode('ground')
        coll_node.set_from_collide_mask(0)
        coll_node.add_solid(coll_solid)
        coll_np = self.np.attach_new_node(coll_node)
        #coll_np.show()

        dlight = DirectionalLight('dlight')
        dlight.setColor(VBase4(1, 1, 1, 1))
        dlnp = self.app.render.attachNewNode(dlight)
        dlnp.setHpr(20, -75, 0)
        self.app.render.setLight(dlnp)

    def get_spawn_points(self):
        spawn_nodes = [sp for sp in self.np.find_all_matches("**/spawn_point*")]
        spawn_points = {}
        for sn in spawn_nodes:
            _, _, idx = sn.name.partition(':')
            idx = int(idx)
            spawn_points[idx] = sn
        sorted_spawn_points = [
            spawn_points[key]
            for key in sorted(spawn_points.keys())
        ]
        return sorted_spawn_points


class Vehicle:
    def __init__(self, app, model_file):
        self.app = app

        model = app.loader.load_model(model_file)



        self.physics_node = BulletRigidBodyNode('vehicle')
        self.physics_node.setLinearDamping(0.5)
        #self.physics_node.setAngularDamping(0.5)
        self.physics_node.setLinearSleepThreshold(0)
        self.physics_node.setAngularSleepThreshold(0)
        self.physics_node.setMass(100.0)
        # mesh = BulletTriangleMesh()
        # for geom_node in model.find_all_matches("**/+GeomNode"):
        #     for geom in geom_node.node().get_geoms():
        #         # import pdb; pdb.set_trace()
        #         mesh.addGeom(geom)
        # shape = BulletTriangleMeshShape(mesh, dynamic=False)
        shape = BulletBoxShape(Vec3(0.5, 0.5, 0.5))
        self.physics_node.addShape(shape)
        self.vehicle = NodePath(self.physics_node)

        z = model.find("fz_repulsor*")
        print(z.getHpr())

        model.reparent_to(self.vehicle)


        self.repulsor_queue = CollisionHandlerQueue()
        self.add_repulsor(Vec3( 0.45,  0.45, -0.0), Vec3( 0.5,  0.5, -1))
        self.add_repulsor(Vec3(-0.45,  0.45, -0.0), Vec3(-0.5,  0.5, -1))
        self.add_repulsor(Vec3( 0.45, -0.45, -0.0), Vec3( 0.5, -0.5, -1))
        self.add_repulsor(Vec3(-0.45, -0.45, -0.0), Vec3(-0.5, -0.5, -1))
        # self.add_repulsor(Vec3( 0.4,  0.4, -0.4), Vec3(0, 0, -1))
        # self.add_repulsor(Vec3(-0.4,  0.4, -0.4), Vec3(0, 0, -1))
        # self.add_repulsor(Vec3( 0.4, -0.4, -0.4), Vec3(0, 0, -1))
        # self.add_repulsor(Vec3(-0.4, -0.4, -0.4), Vec3(0, 0, -1))

        self.repulsors_active = True
        self.gyroscope_active = True

    def np(self):
        return self.vehicle

    def place(self, coordinate, orientation):
        self.vehicle.reparent_to(self.app.render)
        self.vehicle.set_pos(coordinate)
        self.vehicle.set_hpr(orientation)
        self.app.physics_world.attachRigidBody(self.physics_node)

    def toggle_repulsors(self):
        self.repulsors_active = not self.repulsors_active

    def toggle_gyroscope(self):
        self.gyroscope_active = not self.gyroscope_active

    def add_repulsor(self, coord, vec):
        repulsor_solid = CollisionRay(Vec3(0, 0, 0), vec)
        repulsor_node = CollisionNode('repulsor')
        repulsor_node.add_solid(repulsor_solid)
        repulsor_node.set_into_collide_mask(0)
        repulsor_np = self.vehicle.attach_new_node(repulsor_node)
        repulsor_np.set_pos(coord)
        repulsor_np.show()
        self.app.repulsor_traverser.addCollider(
            repulsor_np, self.repulsor_queue,
        )

    def apply_repulsors(self):
        dt = globalClock.dt
        for entry in self.repulsor_queue.entries:
            # Distance below which the repulsor strength is > 0
            activation_distance = 10
            repulsor_feeler = entry.get_surface_point(entry.from_node_path)
            if repulsor_feeler.length() < activation_distance and self.repulsors_active:
                # Direction of the impulse
                impulse_vec = -repulsor_feeler / repulsor_feeler.length()
                # Repulsor power at zero distance
                base_strength = 400
                # Fraction of the repulsor beam above the ground
                activation_frac = repulsor_feeler.length() / activation_distance
                # Effective fraction of repulsors force
                activation = cos(0.5*pi * activation_frac)
                # Effective repulsor force
                strength = activation * base_strength
                # Resulting impulse
                impulse = impulse_vec * strength
                # Apply
                repulsor_pos = entry.from_node_path.get_pos(self.vehicle)
                self.physics_node.apply_impulse(impulse * dt, repulsor_pos)

    def apply_gyroscope(self):
        rot = self.physics_node.get_angular_velocity()
        dt = globalClock.dt
        self.physics_node.apply_torque_impulse(-rot * dt * 50)


    def shock(self):
        #self.physics_node.apply_impulse(
        #    Vec3(0,0,0),
        #    Vec3(random(), random(), random()) * 10,
        #)
        self.physics_node.apply_torque_impulse(
            (Vec3(random(), random(), random()) - Vec3(0.5, 0.5, 0.5)) * 100,
        )


class CameraController:
    def __init__(self, app, camera, vehicle):
        self.app = app
        self.camera = camera
        self.vehicle = vehicle
        self.camera.reparent_to(self.app.render)

    def set_vehicle(self, vehicle):
        self.vehicle = vehicle

    def update(self, task):
        horiz_dist = 30
        cam_offset = Vec3(0, 0, 10)
        focus_offset = Vec3(0, 0, 5)
        vehicle_pos = self.vehicle.np().get_pos(self.app.render)
        vehicle_back = self.app.render.get_relative_vector(
            self.vehicle.np(),
            Vec3(0, -1, 0),
        )
        vehicle_back.z = 0
        vehicle_back = vehicle_back / vehicle_back.length()

        cam_pos = vehicle_pos + vehicle_back * horiz_dist + cam_offset
        focus = vehicle_pos + focus_offset
        base.cam.set_pos(cam_pos)
        base.cam.look_at(focus)

        return task.cont


class VehicleController:
    def __init__(self, app, vehicle):
        self.app = app
        self.vehicle = vehicle
        self.app.accept("n", self.next_vehicle)
        self.app.accept("r", self.toggle_repulsors)
        self.app.accept("g", self.toggle_gyroscope)
        self.app.accept("s", self.shock)

    def next_vehicle(self):
        self.app.next_vehicle()

    def toggle_repulsors(self):
        self.vehicle.toggle_repulsors()

    def toggle_gyroscope(self):
        self.vehicle.toggle_gyroscope()

    def set_vehicle(self, vehicle):
        self.vehicle = vehicle

    def shock(self):
        self.vehicle.shock()


def main():
    app = GameApp()
    app.run()

if __name__ == '__main__':
    main()
