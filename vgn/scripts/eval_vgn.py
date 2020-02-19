import argparse
from pathlib import Path

import open3d
from mayavi import mlab
import numpy as np
from tqdm import tqdm
import torch

from vgn.hand import Hand
from vgn.grasp import from_voxel_coordinates
from vgn.grasp_detector import GraspDetector
from vgn.data_generation import reconstruct_scene
from vgn.simulation import GraspExperiment
from vgn.utils.io import load_dict
from vgn.utils.transform import Transform


def main(args):
    config = load_dict(Path(args.config))
    urdf_root = Path(config["urdf_root"])
    hand_config = load_dict(Path(config["hand_config"]))
    object_set = config["object_set"]
    network_path = Path(config["model_path"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_experiments = 20

    hand = Hand.from_dict(hand_config)
    size = 4 * hand.max_gripper_width

    sim = GraspExperiment(urdf_root, object_set, hand, size, args.sim_gui, args.rtf)
    detector = GraspDetector(device, network_path, show_detections=False)

    outcomes = np.empty(num_experiments, dtype=np.int)
    for i in tqdm(range(num_experiments), ascii=True):
        outcomes[i] = run_trial(sim, detector)

    print_results(outcomes)


def run_trial(sim, detector):
    sim.setup()
    sim.pause()
    tsdf, high_res_tsdf = reconstruct_scene(sim)

    grasps, qualities = detector.detect_grasps(tsdf.get_volume())
    # mlab.show()

    i = np.argmax(qualities)
    grasp = from_voxel_coordinates(grasps[i], Transform.identity(), tsdf.voxel_size)

    sim.resume()
    outcome, width = sim.test_grasp(grasp.pose)

    return outcome


def print_results(outcomes):
    num_trials = len(outcomes)
    num_collision = np.sum(outcomes == 1)
    num_empty = np.sum(outcomes == 2)
    num_slipped = np.sum(outcomes == 3)
    num_success = np.sum(outcomes == 4)

    print("Collision: {}/{}".format(num_collision, num_trials))
    print("Empty:     {}/{}".format(num_empty, num_trials))
    print("Slipped:   {}/{}".format(num_slipped, num_trials))
    print("Success:   {}/{}".format(num_success, num_trials))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="evaluate vgn in simulation")
    parser.add_argument(
        "--config", type=str, required=True, help="experiment configuration file",
    )
    parser.add_argument("--sim-gui", action="store_true", help="disable headless mode")
    parser.add_argument(
        "--rtf", type=float, default=-1.0, help="real time factor of the simulation"
    )
    args = parser.parse_args()
    main(args)
