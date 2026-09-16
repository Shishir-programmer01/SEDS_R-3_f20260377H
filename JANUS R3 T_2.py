import matplotlib.pyplot as plt
import numpy as np


# State = [x position (m), y position (m), altitude (m), heading (rad)].
START_ALTITUDE = 700.0
TARGET = np.array([0.0, 0.0, 0.0])
GLIDE_SPEED = 12.0
SINK_RATE = 1.5
MAX_TURN_RATE = np.deg2rad(25.0)
TURN_GAIN = 2.5


def paraglider_dynamics(state, turn_rate):
    """Simplified steady-glide dynamics used for the path simulation."""
    heading = state[3]
    return np.array([
        GLIDE_SPEED * np.cos(heading),
        GLIDE_SPEED * np.sin(heading),
        -SINK_RATE,
        turn_rate,
    ])


def guidance(state, target):
    """Point the glider toward the target with bounded turn control."""
    direction = target[:2] - state[:2]
    desired_heading = np.arctan2(direction[1], direction[0])
    error = desired_heading - state[3]
    error = np.arctan2(np.sin(error), np.cos(error))
    return np.clip(TURN_GAIN * error, -MAX_TURN_RATE, MAX_TURN_RATE)


def simulate(seed=42):
    """Launch randomly at 700 m and return the simulated trajectory."""
    rng = np.random.default_rng(seed)
    start = np.array([
        rng.uniform(-1000.0, 1000.0),
        rng.uniform(-1000.0, 1000.0),
        START_ALTITUDE,
        rng.uniform(-np.pi, np.pi),
    ])
    state = start.copy()
    trajectory = [state.copy()]
    dt = 0.1

    for _ in range(6000):
        horizontal_distance = np.linalg.norm(state[:2] - TARGET[:2])
        if horizontal_distance <= 10.0 and state[2] <= 10.0:
            trajectory.append(np.array([0.0, 0.0, 0.0, state[3]]))
            print("Target reached!")
            break
        if state[2] <= 0.0:
            print("Glider reached the ground before the target.")
            break
        state += paraglider_dynamics(state, guidance(state, TARGET)) * dt
        state[2] = max(state[2], 0.0)
        trajectory.append(state.copy())

    return np.asarray(trajectory), start


trajectory, start = simulate()
print(f"Start: {start[:3]}")
print(f"Final: {trajectory[-1, :3]}")

figure = plt.figure("Paraglider Guidance")
axes = figure.add_subplot(111, projection="3d")
axes.plot(trajectory[:, 0], trajectory[:, 1], trajectory[:, 2],
          label="Paraglider path")
axes.scatter(0, 0, 0, color="red", marker="*", s=160, label="Target")
axes.scatter(start[0], start[1], start[2],
             color="green", marker="o", s=60, label="Random start")
axes.set_xlabel("X (m)")
axes.set_ylabel("Y (m)")
axes.set_zlabel("Altitude (m)")
axes.set_title("Paraglider Path to Target")
axes.legend()
axes.set_box_aspect((1, 1, 0.7))
plt.show()
