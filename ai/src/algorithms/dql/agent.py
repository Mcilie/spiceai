import os

from tensorflow.python.keras.engine.input_layer import InputLayer
from algorithms.agent_interface import SpiceAIAgent
import random

import numpy as np
import tensorflow as tf
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.optimizers import Adam
from algorithms.dql.memory import ReplayBuffer

tf.keras.backend.set_floatx("float64")

LEARNING_RATE = 0.005
GAMMA = 0.95
EPSILON_INIT = 1.0
EPSILON_DELAY = 0.995
EPSILON_MIN = 0.01
BATCH_SIZE = 256


def softmax(q_values):
    """
    Softmax function to calculate action probabilities

    Args:
        q_values: list of q-values for each action

    Returns:
        list of probabilities for each action
    """
    exp_q_values = np.exp(q_values)
    return exp_q_values / np.sum(exp_q_values)


class Model:
    def __init__(self, state_shape, action_size):
        self.state_shape = state_shape
        self.action_size = action_size
        self.epsilon = EPSILON_INIT

        self.model = self.nn_model()

    def nn_model(self):
        model = tf.keras.Sequential(
            [
                InputLayer(self.state_shape),
                Dense(32, activation="relu"),
                Dense(16, activation="relu"),
                Dense(self.action_size),
            ]
        )
        model.compile(loss="mse", optimizer=Adam(LEARNING_RATE))
        return model

    def predict(self, state: np.ndarray):
        if state.shape != self.state_shape:
            if state.shape[0] == BATCH_SIZE and state.shape[1] == self.state_shape[0]:
                return self.model.predict(state)
            else:
                raise ValueError(
                    f"Wrong state shape: {state.shape}, expected {self.state_shape}"
                )

        state_batch = np.expand_dims(state, axis=0)

        return self.model.predict(state_batch)[0]

    def get_action(self, state: np.ndarray):
        if np.shape(state) != self.state_shape:
            raise ValueError(
                f"Wrong state shape: {state.shape}, expected {self.state_shape}"
            )

        # If epsilon is zero, then don't explore
        if self.epsilon != 0.0:
            self.epsilon *= EPSILON_DELAY
            self.epsilon = max(self.epsilon, EPSILON_MIN)

        q_value = self.predict(state)
        if np.random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1), np.zeros(self.action_size)
        return np.argmax(q_value), softmax(q_value)

    def train(self, states, targets):
        self.model.fit(states, targets, epochs=1)


class DeepQLearning_Agent(SpiceAIAgent):
    def __init__(self, state_shape, action_size):
        self.state_shape = state_shape
        self.action_size = action_size

        self.model = Model(self.state_shape, self.action_size)
        self.target_model = Model(self.state_shape, self.action_size)
        self.update_target()

        self.buffer = ReplayBuffer(BATCH_SIZE)

    def update_target(self):
        weights = self.model.model.get_weights()
        self.target_model.model.set_weights(weights)

    def add_experience(self, state, action, reward, next_state):
        self.buffer.store(state, action, reward, next_state)

    def act(self, state):
        return self.model.get_action(state)

    def save(self, model_path: str):
        self.model.model.save(model_path)

    def load(self, model_path: str) -> bool:
        if os.path.exists(model_path):
            self.model.model = tf.keras.models.load_model(model_path)
            self.update_target()

            # When loading a model, we want to set the epsilon to 0 so that the agent
            # will not explore
            self.model.epsilon = 0.0
            return True
        else:
            return False

    def learn(self):
        if self.buffer.size() >= BATCH_SIZE:
            self.replay_experience()
        self.update_target()

    def replay_experience(self):
        for _ in range(10):
            states, actions, rewards, next_states = self.buffer.sample()
            targets = self.model.predict(states)
            next_q_values = self.target_model.predict(next_states)[
                range(BATCH_SIZE),
                np.argmax(self.model.predict(next_states), axis=1),
            ]
            targets[range(BATCH_SIZE), actions] = rewards + next_q_values * GAMMA
            self.model.train(states, targets)