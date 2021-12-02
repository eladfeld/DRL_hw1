from hw1.agent_interface import AgentInterface
import numpy as np
import tensorflow as tf
from tensorflow.keras.layers import Dense, Input, BatchNormalization, GlobalAvgPool1D, Add , Subtract, Reshape
from tensorflow.keras.models import clone_model, Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import backend as K


class Agent(AgentInterface):
    def __init__(self, environment, args_dict):
        super().__init__(environment, 'dqn_cart')
        self.args = self._read_arguments(args_dict)
        self.epsilon = self.args['epsilon']
        self.epsilon_decay_factor = self.args['epsilon_decay_factor']
        self.epsilon_decay_steps = self.args['epsilon_decay_steps']
        self._check_arguments()
        self.states_shape = environment.get_all_states()
        self.actions = environment.get_all_actions()
        self.environment = environment
        self.actions_indices = {self.actions[i]: i for i in range(len(self.actions))}
        self.value_q_network = None
        self.target_q_network = None
        self.training_model = None
        self.target_update_steps = self.args['target_update_steps']
        self.step = 0
        self.discount_factor = self.args['discount_factor']
        self.learning_rate = self.args['learning_rate']
        self.min_epsilon = args_dict['min_epsilon']
        self.min_lr = args_dict['min_lr']
        self.lr_decay_factor = args_dict['lr_decay_factor']
        self.lr_decay_step = args_dict['lr_decay_step']


    def _read_arguments(self, args_dict):
        possible_args = ['epsilon', 'epsilon_decay_factor', 'epsilon_decay_steps', 'min_epsilon', 'layers',
                         'learning_rate', 'target_update_steps', 'steps', 'discount_factor', 'lr_decay_factor',
                         'lr_decay_step', 'min_lr']
        args = {}
        for key in args_dict.keys():
            if key in possible_args:
                args[key] = args_dict[key]
        return args

    def _check_arguments(self):
        if self.epsilon < 0 or self.epsilon > 1:
            raise ValueError('epsilon value should be between 0 to 1')
        if self.epsilon_decay_factor < 0 or self.epsilon_decay_factor > 1:
            raise ValueError('epsilon_decay_factor value should be between 0 to 1')
        if self.epsilon_decay_steps < 1 or not isinstance(self.epsilon_decay_steps, int):
            raise ValueError('epsilon_decay_steps value should be integer bigger then  1')
        is_valid_layer = lambda l: isinstance(l, int) and l > 0
        if not hasattr(self.args['layers'], '__iter__') or not all([is_valid_layer(l) for l in self.args['layers']]):
            raise ValueError('layers argument should be iterable with positive integer elements')

    def initialize_q(self):
        self.value_q_network = self._build_model()
        self.target_q_network = clone_model(self.value_q_network)
        self.target_q_network.set_weights(self.value_q_network.get_weights())
        self.training_model = self._build_training_model()
        optimizer = Adam(learning_rate=self.learning_rate)
        self.training_model.compile(optimizer, loss='mse')


    def get_action_by_policy(self, state):
        q_for_state = self.value_q_network.predict(np.expand_dims(state, axis=0))
        if not self.train_mode or np.random.uniform(0, 1) > self.epsilon:
            action_index = np.argmax(q_for_state)
        else:
            action_index = np.random.randint(len(self.actions))
        return self.actions[action_index], np.squeeze(q_for_state)[action_index]

    def update_q(self, **kwars):
        states, actions, rewards, new_states, ds = kwars['states'], kwars['actions'], kwars['rewards'],\
                                                   kwars['new_states'], kwars['ds']
        ds = np.asarray(ds)
        actions = np.asarray([self.actions_indices[a] for a in actions], dtype=np.int32)
        rewards = np.asarray(rewards, dtype=np.float64)
        new_states = np.asarray(new_states)
        states = np.asarray(states)
        done_indices = np.where(ds)
        undone_indices = np.where(ds == False)
        ys = np.zeros_like(actions, dtype=np.float64)
        ys[done_indices] += rewards[done_indices]
        q_next = self.get_action_by_max(new_states[undone_indices])
        ys[undone_indices] += rewards[undone_indices] + self.discount_factor * q_next
        ys = ys
        actions = np.concatenate([np.indices(actions.shape).T, np.expand_dims(actions, axis=0).T], axis=1)
        if self.environment.step_num == self.lr_decay_step and self.learning_rate > self.min_lr:
            self.learning_rate = self.lr_decay_factor * self.learning_rate
            K.set_value(self.training_model.optimizer.learning_rate, self.learning_rate)
        loss = self.training_model.train_on_batch(x=[states, actions], y=ys)
        if self.step % 100 == 0:
            print('loss: %1.4f' % loss)
        self.step += 1
        if self.step % self.target_update_steps == 0 or self.step < 50:
            self._update_target()
        if self.step % self.epsilon_decay_steps == 0:
            self._update_epsilon()

    def _update_target(self):
        self.target_q_network.set_weights(self.value_q_network.get_weights())

    def _update_epsilon(self):
        if self.epsilon > self.min_epsilon:
            self.epsilon = self.epsilon * self.epsilon_decay_factor
        if self.epsilon < self.min_epsilon:
            self.epsilon = self.min_epsilon
        print('epsilon: %1.3f' % self.epsilon)

    def get_all_actions(self):
        return self.actions

    def get_action_by_max(self, state):
        q_for_state = self.target_q_network.predict(state)
        return np.max(q_for_state, axis=-1)

    def _build_model(self):
        i = Input(shape=self.states_shape)
        layers = self.args['layers']
        d = i
        for layer in layers:
            d = Dense(layer, activation='relu')(d)
            d = BatchNormalization()(d)
        a = Dense(4, activation='relu')(d)
        a = Dense(len(self.actions), activation='linear')(a)
        a = Reshape(target_shape=(1, a.shape[-1]))(a)
        a_mean = GlobalAvgPool1D()(a)
        a = Subtract()([a, a_mean])
        a = Reshape(target_shape=(a.shape[-1],))(a)
        v = Dense(4, activation='relu')(d)
        v = Dense(1, activation='linear')(v)
        o = Add()([a, v])

        return Model(inputs=i, outputs=o)

    def _build_training_model(self):
        i = Input(shape=self.states_shape)
        a = Input(shape=(2,), dtype='int32')
        o = self.value_q_network(i)
        o = tf.gather_nd(o, a) ## check if its right
        return Model(inputs=[i, a], outputs=[o])

