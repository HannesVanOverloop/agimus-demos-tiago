# {{{2 Imports and argument parsing
from __future__ import print_function
from CORBA import Any, TC_long
from hpp.corbaserver.manipulation import Robot, loadServerPlugin, createContext, newProblem, ProblemSolver, ConstraintGraph, Rule, Constraints, CorbaClient
from hpp.gepetto.manipulation import ViewerFactory
from hpp_idl.hpp import Error as HppError
import sys, argparse, numpy as np, time
try:
    import tqdm
    def progressbar_iterable(iterable, *args, **kwargs):
        return tqdm.tqdm(iterable, *args, **kwargs)
    def progressbar_object(*args, **kwargs):
        return tqdm.tqdm(*args, **kwargs)
except ImportError:
    def progressbar_iterable(iterable, *args, **kwargs):
        return iterable
    def progressbar_object(*args, **kwargs):
        class faketqdm:
            def set_description(*args, **kwargs):
                pass
            def update(*args, **kwargs):
                pass
            def write(s):
                print(s)
        return faketqdm()

# parse arguments
defaultContext = "corbaserver"
p = argparse.ArgumentParser (description=
                             'Initialize demo of Pyrene manipulating a box')
p.add_argument ('--context', type=str, metavar='context',
                default=defaultContext,
                help="identifier of ProblemSolver instance")
p.add_argument ('--n-random-handles', type=int, default=None,
                help="Generate a random model with N handles.")
args = p.parse_args ()
if args.context != defaultContext:
    createContext (args.context)
isSimulation = args.context == "simulation"
# 2}}}

# {{{2 Robot and problem definition

#Robot.urdfFilename = "package://tiago_data/robots/tiago_steel_without_wheels.urdf"
#Robot.srdfFilename = "package://tiago_data/srdf/tiago.srdf"
from hpp.rostools import process_xacro, retrieve_resource
Robot.urdfString = process_xacro("package://tiago_description/robots/tiago.urdf.xacro", "robot:=steel", "end_effector:=pal-hey5", "ft_sensor:=schunk-ft")
Robot.srdfString = ""

if args.n_random_handles is None:
    srdf_cylinder = "package://agimus_demos/srdf/cylinder.srdf"
else:
    from generate_obstacle_model import generate_srdf
    bvh_file = "/home/jmirabel/devel/hpp/src/agimus-demos/meshes/cylinder.stl"
    srdf_cylinder = "/tmp/cylinder.srdf"
    with open(srdf_cylinder, 'w') as output:
        generate_srdf(bvh_file, args.n_random_handles, output)

class Cylinder:
    urdfFilename = "package://agimus_demos/urdf/cylinder.urdf"
    srdfFilename = srdf_cylinder
    rootJointType = "freeflyer"

class Driller:
    urdfFilename = "package://gerard_bauzil/urdf/driller_with_qr_drill.urdf"
    srdfFilename = "package://gerard_bauzil/srdf/driller.srdf"
    rootJointType = "freeflyer"

class PartP72:
    urdfFilename = "package://agimus_demos/urdf/P72-with-table.urdf"
    srdfFilename = "package://agimus_demos/srdf/P72.srdf"
    rootJointType = "freeflyer"

## Reduce joint range for security
def shrinkJointRange (robot, ratio):
    for j in robot.jointNames:
        if j[:6] != "tiago/": continue
        tj = j[6:]
        if tj.startswith("torso") or tj.startswith("arm") or tj.startswith("head"):
            bounds = robot.getJointBounds (j)
            if len (bounds) == 2:
                width = bounds [1] - bounds [0]
                mean = .5 * (bounds [1] + bounds [0])
                m = mean - .5 * ratio * width
                M = mean + .5 * ratio * width
                robot.setJointBounds (j, [m, M])

print("context=" + args.context)
loadServerPlugin (args.context, "manipulation-corba.so")
newProblem()
client = CorbaClient(context=args.context)
client.basic._tools.deleteAllServants()
def wd(o):
    from hpp.corbaserver import wrap_delete
    return wrap_delete(o, client.basic._tools)
client.manipulation.problem.selectProblem (args.context)

robot = Robot("robot", "tiago", rootJointType="planar", client=client)
crobot = wd(wd(robot.hppcorba.problem.getProblem()).robot())

from tiago_fov import TiagoFOV, TiagoFOVGuiCallback
from hpp import Transform
tiago_fov = TiagoFOV(urdfString = Robot.urdfString,
        # Real field of view angles are (49.5, 60),
        fov = np.radians((44.5, 55)),
        geoms = [ "arm_3_link_0" ])
tagss = [ ['driller/tag36_11_00230',], ['part/tag36_11_00006', 'part/tag36_11_00015',]]
tag_sizess = [ [ 0.064, ], [ 0.1615, 0.1615,] ]
tag_size_margin = 0.01
# Apply a margin on the tags
tag_sizess = [ [ s+tag_size_margin for s in sizes ] for sizes in tag_sizess ]
tiago_fov_gui = TiagoFOVGuiCallback(robot, tiago_fov, sum(tagss, []), sum(tag_sizess, []))

qneutral = crobot.neutralConfiguration()
qneutral[robot.rankInConfiguration['tiago/hand_thumb_abd_joint']] = 1.5707
qneutral[robot.rankInConfiguration['tiago/hand_index_abd_joint']]  = 0.35
qneutral[robot.rankInConfiguration['tiago/hand_middle_abd_joint']] = -0.1
qneutral[robot.rankInConfiguration['tiago/hand_ring_abd_joint']]   = -0.2
qneutral[robot.rankInConfiguration['tiago/hand_little_abd_joint']] = -0.35
removedJoints = [
            'tiago/caster_back_left_1_joint',
            'tiago/caster_back_left_2_joint',
            'tiago/caster_back_right_1_joint',
            'tiago/caster_back_right_2_joint',
            'tiago/caster_front_left_1_joint',
            'tiago/caster_front_left_2_joint',
            'tiago/caster_front_right_1_joint',
            'tiago/caster_front_right_2_joint',
            'tiago/suspension_left_joint',
            'tiago/wheel_left_joint',
            'tiago/suspension_right_joint',
            'tiago/wheel_right_joint',

            # Comment this 3 joints otherwise sot is not happy
            #'tiago/hand_index_joint',
            #'tiago/hand_mrl_joint',
            #'tiago/hand_thumb_joint',

            'tiago/hand_index_abd_joint',
            'tiago/hand_index_virtual_1_joint',
            'tiago/hand_index_flex_1_joint',
            'tiago/hand_index_virtual_2_joint',
            'tiago/hand_index_flex_2_joint',
            'tiago/hand_index_virtual_3_joint',
            'tiago/hand_index_flex_3_joint',
            'tiago/hand_little_abd_joint',
            'tiago/hand_little_virtual_1_joint',
            'tiago/hand_little_flex_1_joint',
            'tiago/hand_little_virtual_2_joint',
            'tiago/hand_little_flex_2_joint',
            'tiago/hand_little_virtual_3_joint',
            'tiago/hand_little_flex_3_joint',
            'tiago/hand_middle_abd_joint',
            'tiago/hand_middle_virtual_1_joint',
            'tiago/hand_middle_flex_1_joint',
            'tiago/hand_middle_virtual_2_joint',
            'tiago/hand_middle_flex_2_joint',
            'tiago/hand_middle_virtual_3_joint',
            'tiago/hand_middle_flex_3_joint',
            'tiago/hand_ring_abd_joint',
            'tiago/hand_ring_virtual_1_joint',
            'tiago/hand_ring_flex_1_joint',
            'tiago/hand_ring_virtual_2_joint',
            'tiago/hand_ring_flex_2_joint',
            'tiago/hand_ring_virtual_3_joint',
            'tiago/hand_ring_flex_3_joint',
            'tiago/hand_thumb_abd_joint',
            'tiago/hand_thumb_virtual_1_joint',
            'tiago/hand_thumb_flex_1_joint',
            'tiago/hand_thumb_virtual_2_joint',
            'tiago/hand_thumb_flex_2_joint',
            ]
crobot.removeJoints(removedJoints, qneutral)
tiago_fov.reduceModel(removedJoints, qneutral, len_prefix=len("tiago/"))
del crobot
robot.insertRobotSRDFModel("tiago", "package://tiago_data/srdf/tiago.srdf")
robot.insertRobotSRDFModel("tiago", "package://tiago_data/srdf/pal_hey5_gripper.srdf")
robot.setJointBounds('tiago/root_joint', [-10, 10, -10, 10])
ps = ProblemSolver(robot)
vf = ViewerFactory(ps)

vf.loadRobotModel (Driller, "driller")
robot.insertRobotSRDFModel("driller", "package://gerard_bauzil/srdf/qr_drill.srdf")
robot.setJointBounds('driller/root_joint', [-10, 10, -10, 10, 0, 2])
vf.loadRobotModel (PartP72, "part")
robot.setJointBounds('part/root_joint', [-2, 2, -2, 2, -2, 2])

srdf_disable_collisions_fmt = """  <disable_collisions link1="{}" link2="{}" reason=""/>\n"""
# Disable collision between tiago/hand_safety_box_0 and driller
srdf_disable_collisions = """<robot>"""
srdf_disable_collisions += srdf_disable_collisions_fmt.format("tiago/hand_safety_box", "driller/base_link")
# Disable collision between tiago/hand (except hand_safety_box_0) and all other tiago links
linka, linkb, enabled = robot.hppcorba.robot.autocollisionPairs()
for la, lb, en in zip(linka, linkb, enabled):
    if not en: continue
    caster_vs_other = ('caster' in la or 'caster' in lb)
    hand_vs_other = False
    for l in [la, lb]:
        if l.startswith("tiago/hand_") and l != "tiago/hand_safety_box_0":
            hand_vs_other = True
            break
    if caster_vs_other or hand_vs_other:
        srdf_disable_collisions += srdf_disable_collisions_fmt.format(la[:la.rfind('_')], lb[:lb.rfind('_')])
# Disable collision between caster wheels and anything else
# TODO
srdf_disable_collisions += "</robot>"
robot.client.manipulation.robot.insertRobotSRDFModelFromString("", srdf_disable_collisions)

vf.loadObstacleModel ("package://gerard_bauzil/urdf/gerard_bauzil.urdf", "room")
#vf.loadObstacleModel ("package://agimus_demos/urdf/P72-table.urdf", "table")
# Display Tiago Field of view.
#vf.guiRequest.append( (tiago_fov.loadInGui, {'self':None}))
# Display visibility cones.
vf.addCallback(tiago_fov_gui)

try:
    v = vf.createViewer()
except:
    print("Did not find viewer")

shrinkJointRange(robot, 0.95)

ps.selectPathValidation("Graph-Dichotomy", 0)
ps.selectPathProjector("Progressive", 0.2)
ps.addPathOptimizer("EnforceTransitionSemantic")
ps.addPathOptimizer("SimpleTimeParameterization")
if isSimulation:
    ps.setMaxIterProjection (1)

ps.setParameter("SimpleTimeParameterization/safety", 0.25)
ps.setParameter("SimpleTimeParameterization/order", 2)
ps.setParameter("SimpleTimeParameterization/maxAcceleration", 1.0)
ps.setParameter("ManipulationPlanner/extendStep", 0.7)
ps.setParameter("SteeringMethod/Carlike/turningRadius", 0.05)

q0 = robot.getCurrentConfig()
q0[:4] = [0, -0.9, 0, 1]
#q0[robot.rankInConfiguration['tiago/torso_lift_joint']] = 0.15
q0[robot.rankInConfiguration['tiago/torso_lift_joint']] = 0.34
q0[robot.rankInConfiguration['tiago/arm_1_joint']] = 0.10
q0[robot.rankInConfiguration['tiago/arm_2_joint']] = -1.47
q0[robot.rankInConfiguration['tiago/arm_3_joint']] = -0.16
q0[robot.rankInConfiguration['tiago/arm_4_joint']] = 1.87
q0[robot.rankInConfiguration['tiago/arm_5_joint']] = -1.57
q0[robot.rankInConfiguration['tiago/arm_6_joint']] = 1.3
q0[robot.rankInConfiguration['tiago/arm_7_joint']] = 0.00

q0[robot.rankInConfiguration['part/root_joint']:] = [0,0.3,0.8,0,0,1,0]
# 2}}}

# {{{2 Constraint graph initialization

# {{{3 Constraint definition
def lockJoint(jname, q, cname=None, constantRhs=True):
    if cname is None:
        cname = jname
    s = robot.rankInConfiguration[jname]
    e = s+robot.getJointConfigSize(jname)
    ps.createLockedJoint(cname, jname, q[s:e])
    ps.setConstantRightHandSide(cname, constantRhs)
    return cname

ljs = list()
ps.createLockedJoint("tiago_base", "tiago/root_joint", [0,0,1,0])

lockJoint("part/root_joint", q0, "lock_part", constantRhs=False)
c_lock_part = ps.hppcorba.problem.getConstraint("lock_part")

for n in robot.jointNames:
    if n.startswith('tiago/gripper_') or n.startswith('tiago/hand_'):
        ljs.append(lockJoint(n, q0))

lock_arm = [ lockJoint(n, q0) for n in robot.jointNames
        if n.startswith("tiago/arm") or n.startswith('tiago/torso')]
lock_head = [ lockJoint(n, q0) for n in robot.jointNames
        if n.startswith("tiago/head")]

part_gripper = "driller/drill_tip"
ps.createPositionConstraint("look_at_gripper", "tiago/xtion_rgb_optical_frame", part_gripper,
        (0,0,0), (0,0,0), (True,True,True))
look_at_gripper = ps.hppcorba.problem.getConstraint("look_at_gripper")
import hpp_idl
look_at_gripper.setComparisonType([hpp_idl.hpp.EqualToZero,hpp_idl.hpp.EqualToZero,hpp_idl.hpp.Superior])
ps.createPositionConstraint("look_at_part", "tiago/xtion_rgb_optical_frame", "part/to_tag_100_base",
        (0,0,0), (0,0,0), (True,True,False))
look_at_part = ps.hppcorba.problem.getConstraint("look_at_part")
# 3}}}

# {{{3 Constraint graph instanciation
from hpp.corbaserver.manipulation import ConstraintGraphFactory
graph = ConstraintGraph(robot, 'graph')
factory = ConstraintGraphFactory(graph)
factory.setGrippers([ "tiago/gripper", "driller/drill_tip", ])

all_handles = ps.getAvailable('handle')
part_handles = filter(lambda x: x.startswith("part/"), all_handles)
factory.setObjects([ "driller", "part", ], [ [ "driller/handle", ], part_handles, ], [ [], [] ])

factory.setRules([
    # Forbid driller to grasp itself.
    Rule([ "driller/drill_tip", ], [ "driller/handle", ], False),
    # Tiago always hold the gripper.
    Rule([ "tiago/gripper", ], [ "", ], False), Rule([ "tiago/gripper", ], [ "part/.*", ], False),
    # Allow to associate drill_tip with part holes only.
    Rule([ "tiago/gripper", "driller/drill_tip", ], [ "driller/handle", ".*", ], True), ])
factory.generate()

graph.addConstraints(graph=True, constraints=Constraints(numConstraints=ljs))
free = "tiago/gripper grasps driller/handle"
loop_free = 'Loop | 0-0'
for n in graph.nodes.keys():
    if n == free: continue
    graph.addConstraints(node=n, constraints=Constraints(numConstraints=["look_at_gripper"]))
for e in graph.edges.keys():
    graph.addConstraints(edge=e, constraints=Constraints(numConstraints=["tiago_base"]))

graph.createNode('home', priority=1000)
graph.createEdge('home', 'home', 'move_base')
graph.createEdge('home',  free , 'start_arm', isInNode="home")
graph.createEdge( free , 'home', 'end_arm', isInNode=free)

graph.addConstraints(node="home", constraints=Constraints(numConstraints=lock_arm+lock_head))
graph.addConstraints(edge="end_arm", constraints=Constraints(numConstraints=["tiago_base", "lock_part"]))
graph.addConstraints(edge="move_base", constraints=Constraints(numConstraints=['tiago/gripper grasps driller/handle', "lock_part"]))
graph.addConstraints(edge="start_arm", constraints=Constraints(numConstraints=['tiago/gripper grasps driller/handle', "lock_part"]))

cproblem = ps.hppcorba.problem.getProblem()

cgraph = cproblem.getConstraintGraph()

graph.initialize()
# 3}}}

# {{{3 Constraint graph validation
graphValidation = ps.client.manipulation.problem.createGraphValidation()
graphValidation.validate(cgraph)
if graphValidation.hasErrors():
    print(graphValidation.str())
    print("Graph has infeasibilities")
    sys.exit(1)
elif graphValidation.hasWarnings():
    print(graphValidation.str())
    print("Graph has only warnings")
else:
    print("Graph *seems* valid.")
# 3}}}
# 2}}}

# {{{2 Functions for handling the TSP
def generate_valid_config_for_handle(handle, qinit, qguesses = [], NrandomConfig=10):
    edge = part_gripper + " > " + handle
    ok = False
    from itertools import chain
    def project_and_validate(e, qrhs, q):
        res, qres, err = graph.generateTargetConfig (e, qrhs, q)
        return res and not tiago_fov.clogged(qres, robot, tagss, tag_sizess) and robot.configIsValid(qres), qres
    qpg, qg = None, None
    for qrand in chain(qguesses, ( robot.shootRandomConfig() for _ in range(NrandomConfig) )):
        res, qpg = project_and_validate (edge+" | 0-0_01", qinit, qrand)
        if res:
            ok, qg = project_and_validate(edge+" | 0-0_12", qpg, qpg)
            if ok: break
    return ok, qpg, qg

def generate_valid_config(constraint, qguesses = [], NrandomConfig=10):
    from itertools import chain
    for qrand in chain(qguesses, ( robot.shootRandomConfig() for _ in range(NrandomConfig) )):
        res, qres = constraint.apply (qrand)
        if res and not tiago_fov.clogged(qres, robot, tagss, tag_sizess) and robot.configIsValid(qres):
            return True, qres
    return False, None

class ClusterComputation:
    def __init__(self, cgraph, lock_part):
        self._cgraph = cgraph
        self._lock_part = lock_part

    def freeBaseConstraint(self, hi):
        ni = part_gripper + " > " + hi + " | 0-0_pregrasp"
        cnode = wd(self._cgraph.get(graph.nodes[ni]))
        c = wd(cnode.configConstraint().getConfigProjector()).copy()
        c.add(self._lock_part, 0)
        return c

    def fixedBaseConstraint(self, hi):
        ei = part_gripper + " > " + hi + " | 0-0_01"
        cedge = wd(self._cgraph.get(graph.edges[ei]))
        return wd(cedge.targetConstraint().getConfigProjector())

    def pregraspToGraspConstraint(self, hi):
        ei = part_gripper + " > " + hi + " | 0-0_12"
        cedge = wd(self._cgraph.get(graph.edges[ei]))
        return wd(cedge.targetConstraint().getConfigProjector())

    def find_cluster(self, hi, handles, qrhs, fixed_base=False, pbar=None,
            N_find_first=20,
            N_find_others=20):
        if pbar is None:
            write = print
        else:
            write = pbar.write
        #ni = part_gripper + " grasps " + hi
        #ni = part_gripper + " > " + hi + " | 0-0_pregrasp"
        qrand = q0
        best_cluster = []

        if fixed_base:
            cpi = self.fixedBaseConstraint(hi)
        else:
            cpi = self.freeBaseConstraint(hi)
        cpi.setRightHandSideFromConfig(qrhs)
        ci = self.pregraspToGraspConstraint(hi)

        step = [ False, ] * 4
        for k in range(N_find_first):
            # Compute config where Tiago is collision
            if k == 0:
                res, qphi = generate_valid_config(cpi, qguesses=[q0,], NrandomConfig = 0)
            else:
                res, qphi = generate_valid_config(cpi, qguesses=[], NrandomConfig = 1)
            if not res: continue
            step[0] = True
            ci.setRightHandSideFromConfig(qphi)
            res, qhi = generate_valid_config(ci, qguesses=[qphi,], NrandomConfig = 0)
            if not res: continue
            step[1] = True

            t_base = np.array(robot.hppcorba.robot.getJointsPosition(qhi, ['tiago/torso_fixed_joint'])[0][:3])
            cur_cluster = [ (hi, qphi, qhi) ]
            for hj in handles:
                if hj == hi: continue
                t_handle = np.array(robot.getHandlePositionInJoint(hi)[1][:3])
                if False and np.linalg.norm(t_handle-t_base) > 0.6:
                    #print("prune")
                    continue
                ok, qphj, qhj = generate_valid_config_for_handle(hj, qhi,
                        qguesses = [ qq for _, qq, qqq in cur_cluster ],
                        NrandomConfig=N_find_others)
                if ok:
                    cur_cluster.append((hj, qphj, qhj))
            if len(cur_cluster) > len(best_cluster):
                best_cluster = cur_cluster
                step[2] = True
        if   not step[0]: write("not able to generate pregrasp config")
        elif not step[1]: write("not able to generate grasp config")
        return best_cluster

    def find_clusters(self, handles, qrhs,
            N_find_first=20,
            N_find_others=20):
        from random import choice
        start = time.time()
        clusters = []
        remaining_handles = handles[:]
        pbar = progressbar_object(desc="Looking for clusters", total=len(remaining_handles))
        while remaining_handles:
            cluster = self.find_cluster(choice(remaining_handles), remaining_handles, qrhs,
                    pbar=pbar, N_find_first=N_find_first, N_find_others=N_find_others)
            if len(cluster) == 0: continue
            for hi, qpi, qi in cluster:
                remaining_handles.remove(hi)
            clusters.append(cluster)
            pbar.set_description(desc=str(len(clusters)) + " clusters found", refresh=False)
            pbar.update(len(cluster))
        return clusters

    def solveTSP(self, armPlanner, cluster, qhome = None, pb_kwargs = {}):
        # Create home position
        if qhome is None:
            res, qhome, err = graph.generateTargetConfig('end_arm', cluster[0][1], cluster[0][1])

        configs = [ qhome ]
        grasp_paths = []
        #print(permutation, arm_paths)
        for hi, qphi, qhi in cluster:
            # Compute grasp config
            ei = part_gripper + " > " + hi + " | 0-0_12"
            cedge = wd(self._cgraph.get(graph.edges[ei]))
            p01 = cedge.getSteeringMethod().call(qphi, qhi)
            # from grasp to pregrasp
            eir = part_gripper + " < " + hi + " | 0-0:1-{}_21".format(all_handles.index(hi))
            cedge = wd(self._cgraph.get(graph.edges[eir]))
            p10 = cedge.getSteeringMethod().call(qhi, qphi)

            grasp_paths.append((p01, p10))
            configs.append(qphi)

        if len(configs) == 1: return []
        permutation, arm_paths = armPlanner.solveTSP(configs, resetRoadmapEachTime=True,
                pb_kwargs = pb_kwargs)
        paths = []
        #print(permutation, arm_paths)
        for i, p in zip(permutation[1:], arm_paths):
            # p: path to go to
            # - pregrasp of cluster[i][0] if i > 0
            # - home if i == 0
            paths.append(p)
            if i > 0:
                paths.append(grasp_paths[i-1][0])
                paths.append(grasp_paths[i-1][1])
                # # Compute grasp config
                # hi, qhi = cluster[i-1]
                # ei = part_gripper + " > " + hi + " | 0-0_12"
                # res, qgrasp, err = graph.generateTargetConfig(ei, qhi, qhi)
                # if not res:
                #     throw 
                # assert res, "Could not generate grasp config from pregrasp config."
                # valid, _ = robot.isConfigValid(qgrasp)
                # assert valid, "Grasp config is in collision while pregrasp config is not."
                # # from pregrasp to grasp
                # cedge = wd(self._cgraph.get(graph.edges[ei]))
                # paths.append(cedge.getSteeringMethod().call(qhi, qgrasp))
                # # from grasp to pregrasp
                # eir = part_gripper + " < " + hi + " | 0-{}_21".format(handles.index(hi))
                # cedge = wd(self._cgraph.get(graph.edges[eir]))
                # paths.append(cedge.getSteeringMethod().call(qgrasp, qhi))
        return paths

class InStatePlanner:
    # Default path planner
    plannerType = "BiRRT*"
    optimizerTypes = []
    maxIterPathPlanning = None
    parameters = {'kPRM*/numberOfNodes': Any(TC_long,2000)}

    def __init__(self):

        manipulationProblem = wd(ps.hppcorba.problem.getProblem())
        self.crobot = manipulationProblem.robot()
        # create a new problem with the robot
        self.cproblem = wd(ps.hppcorba.problem.createProblem(self.crobot))
        # Set parameters
        for k, v in self.parameters.items():
            self.cproblem.setParameter(k, v)
        # Set config validation
        self.cproblem.clearConfigValidations()
        for cfgval in [ "CollisionValidation", "JointBoundValidation"]:
            self.cproblem.addConfigValidation(wd(ps.hppcorba.problem.createConfigValidation(cfgval, self.crobot)))
        # get reference to constraint graph
        self.cgraph = manipulationProblem.getConstraintGraph()
        # Add obstacles to new problem
        for obs in ps.getObstacleNames(True,False):
            self.cproblem.addObstacle(wd(ps.hppcorba.problem.getObstacle(obs)))

    def setEdge(self, edge):
        # Get constraint of edge
        edgeLoopFree = wd(self.cgraph.get(graph.edges[edge]))
        self.cconstraints = wd(edgeLoopFree.pathConstraint())
        self.cproblem.setPathValidation(edgeLoopFree.getPathValidation())
        self.cproblem.setConstraints(self.cconstraints)
        self.cproblem.setSteeringMethod(wd(edgeLoopFree.getSteeringMethod()))
        self.cproblem.filterCollisionPairs()

    def setReedsAndSheppSteeringMethod(self):
        sm = wd(ps.hppcorba.problem.createSteeringMethod("ReedsShepp", self.cproblem))
        self.cproblem.setSteeringMethod(sm)
        dist = ps.hppcorba.problem.createDistance("ReedsShepp", self.cproblem)
        self.cproblem.setDistance(dist)

    def buildRoadmap(self, qinit):
        wd(self.cconstraints.getConfigProjector()).setRightHandSideFromConfig(qinit)
        self.cproblem.setInitConfig(qinit)
        self.cproblem.resetGoalConfigs()
        self.roadmap = wd(ps.client.manipulation.problem.createRoadmap(
                wd(self.cproblem.getDistance()),
                self.crobot))
        self.roadmap.constraintGraph(self.cgraph)
        self.planner = wd(ps.hppcorba.problem.createPathPlanner(
            self.plannerType,
            self.cproblem,
            self.roadmap))
        if self.maxIterPathPlanning:
            self.planner.maxIterations(self.maxIterPathPlanning)
        path = wd(self.planner.solve())
        
    def createEmptyRoadmap(self):
        self.roadmap = wd(ps.hppcorba.problem.createRoadmap(
                wd(self.cproblem.getDistance()),
                self.crobot))
        
    def computePath(self, qinit, qgoal, resetRoadmap = False):
        wd(self.cconstraints.getConfigProjector()).setRightHandSideFromConfig(qinit)
        res, qgoal2 = self.cconstraints.apply(qgoal)
        self.cproblem.setInitConfig(qinit)
        self.cproblem.resetGoalConfigs()
        self.cproblem.addGoalConfig(qgoal2)

        if resetRoadmap or not hasattr(self, 'roadmap'):
            self.createEmptyRoadmap()
        self.planner = wd(ps.hppcorba.problem.createPathPlanner(
            self.plannerType,
            self.cproblem,
            self.roadmap))
        if self.plannerType == "BiRRT*":
            self.planner.maxIterations(1000)
        path = wd(self.planner.solve())
        for optType in self.optimizerTypes:
            optimizer = wd(ps.hppcorba.problem.createPathOptimizer(optType, self.cproblem))
            try:
                optpath = optimizer.optimize(path)
                # optimize can return path if it couldn't find a better one.
                # In this case, we have too different client refering to the same servant.
                # thus the following code deletes the old client, which triggers deletion of
                # the servant and the new path points to nothing...
                # path = wd(optimizer.optimize(path))
                from hpp.corbaserver.tools import equals
                if not equals(path, optpath):
                    path = wd(optpath)
            except HppError as e:
                print(e)
        return path

    def solveTSP(self, configs, resetRoadmapEachTime, pb_kwargs={}):
        # Compute matrix of paths
        l = len(configs)
        paths = [ [ None, ] * l for _ in range(l) ]
        distances = np.zeros((l,l))
        from itertools import combinations
        pbar = progressbar_object(desc="Computing distance matrix", total=l*(l-1)/2, **pb_kwargs)
        for i, j in combinations(range(l), 2):
            try:
                path = paths[i][j] = self.computePath(configs[i],configs[j],resetRoadmap=resetRoadmapEachTime)
                distances[j,i] = distances[i,j] = path.length()
            except Exception as e:
                pbar.write("Failed to connect {} to {}: {}".format(i, j,e))
                paths[i][j] = None
                distances[j,i] = distances[i,j] = 1e8
            pbar.update()
        if l > 15:
            from agimus_demos.pytsp.approximative_kopt import solve_3opt as solve_tsp
        else:
            from agimus_demos.pytsp.dynamic_programming import solve_with_heuristic as solve_tsp
        distance, permutation = solve_tsp(distances)
        # rotate permutation so that 0 is the first index.
        solution = []
        permutation = [0,] + permutation + [0,]
        assert permutation[0] == 0, str(permutation[0]) + " should be 0"
        for i,j in zip(permutation,permutation[1:]):
            p = paths[i][j] if i < j else wd(paths[j][i].reverse())
            solution.append(p)
        return permutation, solution

    def writeRoadmap(self, filename):
        ps.client.manipulation.problem.writeRoadmap\
                       (filename, self.roadmap, self.crobot, self.cgraph)

    def readRoadmap(self, filename):
        self.roadmap = ps.client.manipulation.problem.readRoadmap\
                       (filename, self.crobot, self.cgraph)

def concatenate_paths(paths):
    if len(paths) == 0: return None
    p = paths[0].asVector()
    for q in paths[1:]:
        p.appendPath(q)
    return p
# 2}}}

# {{{2 Problem resolution

# {{{3 Finalize FOV filter
res, q, err = graph.applyNodeConstraints(free, q0)
assert res
robot.setCurrentConfig(q)
oMh, oMd = robot.hppcorba.robot.getJointsPosition(q, ["tiago/hand_tool_link", "driller/base_link"])
tiago_fov.appendUrdfModel(Driller.urdfFilename, "hand_tool_link",
        (Transform(oMh).inverse() * Transform(oMd)).toTuple(),
        prefix="driller/")
# 3}}}

# {{{3 Create InStatePlanner
armPlanner = InStatePlanner ()
armPlanner.setEdge(loop_free)
# Set collision margin between mobile base and the rest because the collision model is not correct.
bodies = ("tiago/torso_fixed_link_0", "tiago/base_link_0")
cfgVal = wd(armPlanner.cproblem.getConfigValidations())
pathVal = wd(armPlanner.cproblem.getPathValidation())
for _, la, lb, _, _ in zip(*robot.distancesToCollision()):
    if la in bodies or lb in bodies:
        cfgVal.setSecurityMarginBetweenBodies(la, lb, 0.07)
        pathVal.setSecurityMarginBetweenBodies(la, lb, 0.07)
del cfgVal
del pathVal

basePlanner = InStatePlanner ()
basePlanner.plannerType = "kPRM*"
basePlanner.optimizerTypes.append("RandomShortcut")
basePlanner.setEdge("move_base")
basePlanner.setReedsAndSheppSteeringMethod()

import security_margins
smBase = security_margins.SecurityMargins(robot.jointNames)
margin = 0.1
for i in [ 0, smBase.jid("part/root_joint") ]:
    smBase.margins[i,:] = margin
    smBase.margins[:,i] = margin
basePlanner.cproblem.setSecurityMargins(smBase.margins.tolist())

basePlanner.createEmptyRoadmap()
# 3}}}

# {{{3 Load (or create) mobile base roadmap
basePlannerUsePrecomputedRoadmap = False
if basePlannerUsePrecomputedRoadmap:
    from os import getcwd, path
    roadmap_file = getcwd() + "/roadmap-hpp.bin"
    if path.exists(roadmap_file):
        print("Reading mobile base roadmap", roadmap_file)
        basePlanner.readRoadmap(roadmap_file)
    else:
        print("Building mobile base roadmap")
        try:
            basePlanner.cproblem.setParameter('kPRM*/numberOfNodes', Any(TC_long,2000))
            basePlanner.buildRoadmap(q0)
            #sm.margins[:,:] = 0.
            #basePlanner.cproblem.setSecurityMargins(sm.margins.tolist())
        except HppError as e:
            print(e)
        print("Writing mobile base roadmap", roadmap_file)
        basePlanner.writeRoadmap(roadmap_file)

basePlanner.plannerType = "BiRRT*"
# 3}}}

# {{{3 Find handle clusters and solve TSP for each clusters.
clusters_comp = ClusterComputation(armPlanner.cgraph, c_lock_part)
clusters = clusters_comp.find_clusters(part_handles, q0,
        N_find_first = 40, N_find_others = 40)
#clusters = find_clusters(part_handles[:3], q0)
solve_tsp_problems = False
if solve_tsp_problems:
    clusters_path = []
    qhomes = [q0, ]
    for cluster in progressbar_iterable(clusters, "Find path for each cluster"):
        paths = clusters_comp.solveTSP(armPlanner, cluster, pb_kwargs={'position': 1})

        clusters_path.append(concatenate_paths(paths))
        if len(paths) > 0:
            qhomes.append(paths[0].initial())
# 3}}}

# {{{3 Solve TSP for the mobile base
if solve_tsp_problems:
    base_order, base_paths = basePlanner.solveTSP(qhomes, resetRoadmapEachTime=not basePlannerUsePrecomputedRoadmap)
# }}}

# 2}}}

# {{{2 Function for online resolution
def compute_base_path_to_cluster_init(i_cluster, qcurrent = None):
    if qcurrent is None:
        import estimation 
        qcurrent = estimation.get_current_config(robot, graph, q0[:])
    if not robot.configIsValid(qcurrent): print("qcurrent invalid")

    # Tuck arm.
    res, qtuck, err = graph.generateTargetConfig('end_arm', qcurrent, qcurrent)
    if not res: print("failed to tuck arm")
    if not robot.configIsValid(qtuck): print("qtuck invalid")
    tuckpath = armPlanner.computePath(qcurrent, qtuck, resetRoadmap=True)
    # Move mobile base.
    qhome = clusters[i_cluster][0][1][:4] + qtuck[4:]
    res, qhome, err = graph.generateTargetConfig('move_base', qhome, qhome)
    if not res: print("failed to move base")
    basepath = basePlanner.computePath(qtuck, qhome, resetRoadmap=not basePlannerUsePrecomputedRoadmap)

    # Move the head.
    # Compute config where the robot looks at the part
    constraints = wd(armPlanner.cconstraints.getConfigProjector().copy())
    constraints.add(look_at_part, 0)
    constraints.setRightHandSideFromConfig(qhome)
    res, qend = constraints.apply(qhome)
    if not res: print("failed to look at the part. It may not be visible.")
    headpath = armPlanner.computePath(qhome, qend, resetRoadmap=True)

    tuckpath.concatenate(basepath)
    tuckpath.concatenate(headpath)
    return tuckpath

def compute_path_for_cluster(i_cluster, qcurrent = None):
    if qcurrent is None:
        import estimation 
        qcurrent = estimation.get_current_robot_and_cylinder_config(robot, graph, q0[:])

    cluster = clusters[i_cluster]

    # Recompute a configuration for each handle
    new_cluster = []
    for hi, qphi, qhi in cluster:
        ok, qphi2, qhi2 = generate_valid_config_for_handle(hi, qcurrent,
                qguesses = [qphi,qcurrent,] + [ qpg for _, qpg, qg in new_cluster ],
                NrandomConfig=15)
        if ok:
            new_cluster.append( (hi, qphi2, qhi2) )
        else:
            print("Could not reach handle", hi)

    if len(new_cluster) == 0: return None, None

    paths = clusters_comp.solveTSP(armPlanner, new_cluster, qhome=qcurrent)
    return new_cluster, concatenate_paths(paths)
# 2}}}

# vim: foldmethod=marker foldlevel=1
