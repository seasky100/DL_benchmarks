import json
from pathlib import Path
from importlib import import_module
from pip import get_installed_distributions

import numpy as np
from sacred import Experiment
from sacred.observers import FileStorageObserver

from benchmark.data import Iterator

ex = Experiment('benchmark')
project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / 'results'
ex.observers.append(FileStorageObserver.create(str(data_dir)))


@ex.config
def config():
    """

    """
    project_root = str(project_root)
    ngpu = 0 ### ngpu = 0 corresponds to cpu-mode
    data_type = 'image'

    assert data_type in ['image', 'sequence'], \
        "Your data_type[{}] is not supported.".format(data_type)
    
    data_config = dict(
        image_shape = (3, 28, 28), # (channel, witdth, height)
        sequence_shape = 28, # feature
        niteration = 10,
        batch_size = 10,
        label_size = 3000,
    )
    progressbar = True
    framework = 'torch'
    dnn_arch = 'CNN'

    opt_type = 'SGD'
    opt_conf = dict(
        lr = 0.01,
        momentum = 0.9
        )
        
    assert dnn_arch in ['CNN', 'DNN', 'RNN', 'LSTM',
                         'BLSTM', 'GRU', 'AlexNet', 'ResNet', 'VGG16'], \
                         "Your dnn_arch[{}] is not supported.\n".format(dnn_arch) 

    rnn_layers = 4
    framework_version = None
    assert framework in ['torch', 'mxnet', 'chainer', 'caffe2',
                         'cntk', 'tensorflow', 'dynet', 'nnabla', 'neon'], \
                         "Your framework[{}] is not supported.\n".format(framework) 
    if framework == "torch":
        import torch
        _framework_version = torch.__version__

@ex.capture
def get_iterator(data_type, data_config, progressbar):
    iterator = Iterator(data_type, **data_config)
    if progressbar:
        from tqdm import tqdm
        iterator = tqdm(iterator)
    return iterator


@ex.capture
def get_model(module, data_type, data_config, dnn_arch, rnn_layers):
    if data_type == 'image':
        channel, xdim, ydim = data_config['image_shape']
        output_num = data_config['label_size']
        gpu_mode = True if ngpu >= 1 else False
        if dnn_arch == 'CNN':
            model = module.CNN(channel, xdim, ydim, output_num, gpu_mode)
    elif data_type == "sequence":
        pass
    return model


@ex.capture
def get_trainer(module, model, ngpu):
    trainer = module.Trainer(model, ngpu)
    return trainer


@ex.capture
def get_trainer(_config, framework, framework_version, ngpu):
    package_name_list = [i.project_name for i in
                         get_installed_distributions(local_only=True)]
    package_version_list = [i.version for i in
                            get_installed_distributions(local_only=True)]
    model = None
    if framework == 'torch':
        import torch
        idx = package_name_list.index('torch')
        module = import_module('benchmark.models.th') 
        model = get_model(module=module)
        trainer = get_trainer(module=module, model=model)
    elif framework == 'mxnet':
        idx = package_name_list.index('mxnet-cu80')
        module = import_module('benchmark.models.mx')
        model = get_model(module=module)
    elif framework == 'chainer':
        idx = package_name_list.index('chainer')
        module = import_module('benchmark.models.ch')
        model = get_model(module=module)
    elif framework == 'tensorflow':
        idx = package_name_list.index('tensorflow-gpu')
        module = import_module('benchmark.models.th')
        model = get_model(module=module)
    else:
        raise ValueError
    _config["framework_version"] = package_version_list[idx]
    return trainer


@ex.capture
def train(trainer, iterator, opt_type, opt_conf):
    trainer.set_optimizer(opt_type, opt_conf)            
    results = trainer.train(iterator)
    dump_results(results=results)


@ex.command
def setup():
    pass


@ex.capture
def dump_config(_config, _run):
    exp_dir = data_dir / str(_run._id)
    config_file = exp_dir / "config.json"
    with config_file.open('w') as fp:
        json.dump(_config, fp, indent=4)


@ex.capture
def dump_results(_config, _run, results):
    exp_dir = data_dir / str(_run._id)
    config_file = exp_dir / "results.json"
    with config_file.open('w') as fp:
        json.dump(results, fp, indent=4)


@ex.automain
def main(_run, _config, project_root, framework):
    iterator = get_iterator()
    trainer = get_trainer()
    train(trainer=trainer, iterator=iterator)
    dump_config()
