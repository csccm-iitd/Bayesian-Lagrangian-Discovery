# Hamiltonian Neural Networks | 2019
# Sam Greydanus, Misko Dzamba, Jason Yosinski

import torch, argparse
import numpy as np

import os, sys
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PARENT_DIR)

from nn_models import MLP
from hnn import HNN
from data_cqd import get_dataset
from utils import L2_loss, rk4

def get_args():
    parser = argparse.ArgumentParser(description=None)
    parser.add_argument('--input_dim', default=2, type=int, help='dimensionality of input tensor')
    parser.add_argument('--hidden_dim', default=200, type=int, help='hidden dimension of mlp')
    parser.add_argument('--learn_rate', default=1e-3, type=float, help='learning rate')
    parser.add_argument('--nonlinearity', default='tanh', type=str, help='neural net nonlinearity')
    parser.add_argument('--batch_size', default=1000, type=int, help='batch_size')
    parser.add_argument('--total_steps', default=5000, type=int, help='number of gradient steps')
    parser.add_argument('--print_every', default=50, type=int, help='number of gradient steps between prints')
    parser.add_argument('--name', default='cqd', type=str, help='only one option right now')
    parser.add_argument('--baseline', dest='baseline', action='store_true', help='run baseline or experiment?')
    parser.add_argument('--use_rk4', dest='use_rk4', action='store_true', help='integrate derivative with RK4')
    parser.add_argument('--verbose', default=True, action='store_true', help='verbose?')
    parser.add_argument('--field_type', default='solenoidal', type=str, help='type of vector field to learn')
    parser.add_argument('--seed', default=0, type=int, help='random seed')
    parser.add_argument('--save_dir', default=THIS_DIR, type=str, help='where to save the trained model')
    parser.set_defaults(feature=True)
    return parser.parse_args()

def train(args):
    # set random seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
      
    # init model and optimizer
    if args.verbose:
      print("Training baseline model:" if args.baseline else "Training HNN model:")
      
    output_dim = args.input_dim if args.baseline else 2
    nn_model = MLP(args.input_dim, args.hidden_dim, output_dim, args.nonlinearity)
    model = HNN(args.input_dim, differentiable_model=nn_model,
                field_type=args.field_type, baseline=args.baseline)
    optim = torch.optim.Adam(model.parameters(), args.learn_rate, weight_decay=1e-4)
      
    # arrange data
    data = get_dataset(args.name, args.save_dir, seed=args.seed)
    x = torch.tensor( data['x'], requires_grad=True, dtype=torch.float32)
    test_x = torch.tensor( data['test_x'], requires_grad=True, dtype=torch.float32)
    dxdt = torch.Tensor(data['dx'])
    test_dxdt = torch.Tensor(data['test_dx'])
      
    # vanilla train loop
    stats = {'train_loss': [], 'test_loss': []}
    for step in range(args.total_steps+1):
      
        # train step    
        ixs = torch.randperm(x.shape[0])[:args.batch_size]
        dxdt_hat = model.rk4_time_derivative(x[ixs]) if args.use_rk4 else model.time_derivative(x[ixs])
        loss = L2_loss(dxdt[ixs], dxdt_hat)
        loss.backward() ; optim.step() ; optim.zero_grad()
        
        # run test data
        test_ixs = torch.randperm(test_x.shape[0])[:args.batch_size]
        test_dxdt_hat = model.rk4_time_derivative(test_x[test_ixs]) if args.use_rk4 else model.time_derivative(test_x[test_ixs])
        test_loss = L2_loss(test_dxdt[test_ixs], test_dxdt_hat)
        
        # logging
        stats['train_loss'].append(loss.item())
        stats['test_loss'].append(test_loss.item())
        if args.verbose and step % args.print_every == 0:
          print("step {}, train_loss {:.4e}, test_loss {:.4e}".format(step, loss.item(), test_loss.item()))

    train_dxdt_hat = model.time_derivative(x)
    train_dist = torch.norm(dxdt - train_dxdt_hat)/torch.norm(dxdt)
    test_dxdt_hat = model.time_derivative(test_x)
    test_dist = torch.norm(test_dxdt - test_dxdt_hat)/torch.norm(test_dxdt)
    print('Final train loss {:.4f},\nFinal test loss {:.4f}'
          .format(100*train_dist, 100*test_dist))
    
    return model, stats

# %% Train
args = get_args()
model, stats = train(args)

# save
# os.makedirs(args.save_dir) if not os.path.exists(args.save_dir) else None
# label = '-baseline' if args.baseline else '-hnn'
# label = '-rk4' + label if args.use_rk4 else label
# path = '{}/{}{}.tar'.format(args.save_dir, args.name, label)
# torch.save(model.state_dict(), path)

