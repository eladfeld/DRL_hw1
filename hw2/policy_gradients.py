import random
random.seed(1)
import numpy as np
np.random.seed(1)
import tensorflow.compat.v1 as tf
tf.random.set_random_seed(1)
import gym
# import tensorflow.compat.v1.summary.FileWriter
import collections
import os
tf.disable_v2_behavior()


env = gym.make('CartPole-v1')

class PolicyNetwork:
    def __init__(self, state_size, action_size, learning_rate, name='policy_network'):
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate

        with tf.variable_scope(name):

            self.state = tf.placeholder(tf.float32, [None, self.state_size], name="state")
            self.baseline = tf.placeholder(tf.float32, [None, 1], name="state")
            self.action = tf.placeholder(tf.int32, [self.action_size], name="action")
            self.R_t = tf.placeholder(tf.float32, name="total_rewards")

            self.W1 = tf.get_variable("W1", [self.state_size, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b1 = tf.get_variable("b1", [12], initializer=tf.zeros_initializer())
            self.W2 = tf.get_variable("W2", [12, self.action_size], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b2 = tf.get_variable("b2", [self.action_size], initializer=tf.zeros_initializer())

            self.Z1 = tf.add(tf.matmul(self.state, self.W1), self.b1)
            self.A1 = tf.nn.relu(self.Z1)
            self.output = tf.add(tf.matmul(self.A1, self.W2), self.b2)

            # Softmax probability distribution over actions
            self.actions_distribution = tf.squeeze(tf.nn.softmax(self.output))
            # Loss with negative log probability
            self.neg_log_prob = tf.nn.softmax_cross_entropy_with_logits_v2(logits=self.output, labels=self.action)
            self.R_t_no_base_line = tf.subtract(self.R_t, self.baseline)
            self.loss = tf.reduce_mean(self.neg_log_prob * self.R_t_no_base_line)
            self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

class ValueNetwork:
    def __init__(self, state_size, learning_rate, name='value_network'):
        self.state_size = state_size
        self.learning_rate = learning_rate

        with tf.variable_scope(name):

            self.state = tf.placeholder(tf.float32, [None, self.state_size], name="state")
            self.R_t = tf.placeholder(tf.float32, name="total_rewards")

            self.W1 = tf.get_variable("W1", [self.state_size, 12], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b1 = tf.get_variable("b1", [12], initializer=tf.zeros_initializer())
            self.W2 = tf.get_variable("W3", [12, 1], initializer=tf.keras.initializers.glorot_normal(seed=0))
            self.b2 = tf.get_variable("b3", [1], initializer=tf.zeros_initializer())

            self.Z1 = tf.add(tf.matmul(self.state, self.W1), self.b1)
            self.A1 = tf.nn.relu(self.Z1)
            self.output = tf.add(tf.matmul(self.A1, self.W2), self.b2)


            # Softmax probability distribution over actions
            self.l = tf.nn.l2_loss(tf.subtract(self.output, self.R_t))
            self.loss = tf.reduce_mean(self.l)
            self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)


# Define hyperparameters
state_size = 5
action_size = env.action_space.n

max_episodes = 5000
max_steps = 501
discount_factor = 0.99
learning_rate = 0.0004

render = False

# Initialize the actor network
tf.reset_default_graph()
policy = PolicyNetwork(state_size, action_size, learning_rate)
value = ValueNetwork(state_size, learning_rate)

# tensorboard logs
policy_loss_placeholder = tf.compat.v1.placeholder(tf.float32)
tf.compat.v1.summary.scalar(name="policy_loss", tensor=policy_loss_placeholder)
value_loss_placeholder = tf.compat.v1.placeholder(tf.float32)
tf.compat.v1.summary.scalar(name="value_loss", tensor=value_loss_placeholder)
reward_placeholder = tf.compat.v1.placeholder(tf.float32)
tf.compat.v1.summary.scalar(name="reward", tensor=reward_placeholder)
avg_reward_placeholder = tf.compat.v1.placeholder(tf.float32)
tf.compat.v1.summary.scalar(name="avg_reward", tensor=avg_reward_placeholder)
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.isdir(log_path):
    os.mkdir(log_path)
writer = tf.compat.v1.summary.FileWriter(log_path)
summaries = tf.compat.v1.summary.merge_all()
print('saving logs to: %s' % log_path)

# Start training the agent with REINFORCE algorithm
with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    solved = False
    Transition = collections.namedtuple("Transition", ["state", "action", "reward", "next_state", "done", "baseline"])
    episode_rewards = np.zeros(max_episodes)
    average_rewards = 0.0

    for episode in range(max_episodes):
        state = env.reset()
        state = np.concatenate([state, np.asarray([0])])
        state = state.reshape([1, state_size])
        episode_transitions = []

        for step in range(max_steps):
            baseline = sess.run(value.output, {value.state: state})
            actions_distribution = sess.run(policy.actions_distribution, {policy.state: state, policy.baseline:baseline})
            action = np.random.choice(np.arange(len(actions_distribution)), p=actions_distribution)
            next_state, reward, done, _ = env.step(action)
            next_state = np.concatenate([next_state, np.asarray([(step + 1) / max_steps])])
            next_state = next_state.reshape([1, state_size])
            if render:
                env.render()

            action_one_hot = np.zeros(action_size)
            action_one_hot[action] = 1
            episode_transitions.append(Transition(state=state, action=action_one_hot, reward=reward,
                                                  next_state=next_state, done=done, baseline=baseline))
            episode_rewards[episode] += reward

            if done:
                if episode > 98:
                    # Check if solved
                    average_rewards = np.mean(episode_rewards[(episode - 99):episode+1])
                print("Episode {} Reward: {} Average over 100 episodes: {}".format(episode, episode_rewards[episode], round(average_rewards, 2)))
                if average_rewards > 475:
                    print(' Solved at episode: ' + str(episode))
                    solved = True
                break
            state = next_state

        if solved:
            break

        # Compute Rt for each time-step t and update the network's weights
        policy_losses = []
        value_losses = []
        for t, transition in enumerate(episode_transitions):
            total_discounted_return = sum(discount_factor ** i * t.reward for i, t in enumerate(episode_transitions[t:])) # Rt
            value_feed_dict = {value.state: transition.state, value.R_t: total_discounted_return}
            _, value_loss = sess.run([value.optimizer, value.loss], value_feed_dict)
            policy_feed_dict = {policy.state: transition.state, policy.R_t: total_discounted_return,
                                policy.action: transition.action, policy.baseline: transition.baseline}
            _, policy_loss = sess.run([policy.optimizer, policy.loss], policy_feed_dict)
            policy_losses.append(policy_loss)
            value_losses.append(value_loss)
        avg_value_loss = np.mean(value_losses)
        avg_policy_loss = np.mean(policy_losses)

        summery = sess.run(summaries, feed_dict={policy_loss_placeholder: avg_policy_loss,
                                                 value_loss_placeholder: avg_value_loss,
                                                 reward_placeholder: episode_rewards[episode],
                                                 avg_reward_placeholder: average_rewards if episode > 98 else 0})
        writer.add_summary(summery, global_step=episode)
