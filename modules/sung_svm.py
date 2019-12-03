from matplotlib import pyplot as plt
from sklearn.datasets import load_iris

def plot(x_index, y_index):
    formatter = plt.FuncFormatter(lambda i, *args: iris.target_names[int(i)])
    plt.scatter(iris.data[:, x_index], iris.data[:, y_index], c=iris.target)
    plt.colorbar(ticks=[0, 1, 2], format=formatter)
    plt.xlabel(iris.feature_names[x_index])
    plt.ylabel(iris.feature_names[y_index])

iris = load_iris()
plt.figure(figsize=(14, 4))
plt.subplot(121)
plot(0, 1)
plt.subplot(122)
plot(2, 3)
plt.show()
#
#
# y = iris.target.copy()
# for i in range(len(y)):
#     if y[i] == 0: y[i] = 1
#     else: y[i] = -1
# X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
#
# w = torch.autograd.Variable(torch.rand(dim), requires_grad=True)
# b = torch.autograd.Variable(torch.rand(1),   requires_grad=True)
#
# step_size = 1e-3
# num_epochs = 5000
# minibatch_size = 20
#
# for epoch in range(num_epochs):
#     inds = [i for i in range(len(X_train))]
#     shuffle(inds)
#     for i in range(len(inds)):
#         L = max(0, 1 - y_train[inds[i]] * (torch.dot(w, torch.Tensor(X_train[inds[i]])) - b))**2
#         if L != 0: # if the loss is zero, Pytorch leaves the variables as a float 0.0, so we can't call backward() on it
#             L.backward()
#             w.data -= step_size * w.grad.data # step
#             b.data -= step_size * b.grad.data # step
#             w.grad.data.zero_()
#             b.grad.data.zero_()
#
#
# def accuracy(X, y):
#     correct = 0
#     for i in range(len(y)):
#         y_predicted = int(np.sign((torch.dot(w, torch.Tensor(X[i])) - b).detach().numpy()[0]))
#         if y_predicted == y[i]: correct += 1
#     return float(correct)/len(y)
#
# print('train accuracy', accuracy(X_train, y_train))
# print('test accuracy', accuracy(X_test, y_test))
#
# def line_func(x, offset):
#     return   -1 * (offset - b.detach().numpy()[0] + w.detach().numpy()[0] * x ) / w.detach().numpy()[1]
#
# x = np.array(range(1, 5))
# ym = line_func(x,  0)
# yp = line_func(x,  1)
# yn = line_func(x, -1)
#
# x_index = 2
# y_index = 3
# plt.figure(figsize=(8, 6))
# formatter = plt.FuncFormatter(lambda i, *args: iris.target_names[int(i)])
# plt.scatter(iris.data[:, x_index], iris.data[:, y_index], c=iris.target)
# plt.colorbar(ticks=[0, 1, 2], format=formatter)
# plt.xlabel(iris.feature_names[x_index])
# plt.ylabel(iris.feature_names[y_index])
# plt.plot(x, ym)
# plt.plot(x, yp)
# plt.plot(x, yn)
