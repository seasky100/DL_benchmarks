import json
from pathlib import Path
from importlib import import_module
from pip import get_installed_distributions

import numpy as np
from tqdm import tqdm
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
    ngpu = 1 ### ngpu = 0 corresponds to cpu-mode
    data_type = 'image'

    assert data_type in ['image', 'sequence'], \
        "Your data_type[{}] is not supported.".format(data_type)

    batch_size = 10
    data_options = dict(
        image_shape = (3, 28, 28), # (channel, witdth, height)
        sequence_shape = 28, # feature
        niteration = 1000,
        batch_size = batch_size,
        label_size = 3000,
        target_type = None
    )
    progressbar = True
    framework = 'torch'
    dnn_arch = 'CNN'

    opt_type = 'SGD'
    opt_conf = dict(
        lr = 0.01,
        momentum = 0.9
        )

    trainer_options = dict(
        mode='train',
        benchmark_mode=True,
        half=False,
        )
    time_options = 'total'

    assert time_options in ['total', 'forward', 'backward'], \
        "Your time_options[{}] is not supported.\n".format(dnn_arch) 
    
    assert dnn_arch in ['CNN', 'DNN', 'RNN', 'LSTM',
                         'BLSTM', 'GRU', 'AlexNet', 'ResNet', 'VGG16'], \
                         "Your dnn_arch[{}] is not supported.\n".format(dnn_arch) 

    rnn_layers = 4
    framework_version = None
    assert framework in ['torch', 'mxnet', 'chainer', 'caffe2',
                         'cntk', 'tensorflow', 'dynet', 'nnabla', 'neon'], \
                         "Your framework[{}] is not supported.\n".format(framework)
    package_name_list = [i.project_name for i in
                         get_installed_distributions(local_only=True)]
    package_version_list = [i.version for i in
                            get_installed_distributions(local_only=True)]

    
    if framework == 'torch':    
        idx = package_name_list.index('torch')
    elif framework == 'mxnet':
        idx = package_name_list.index('mxnet')
        package_name = 'mxnet'
    elif framework == 'chainer':
        idx = package_name_list.index('chainer')
    elif framework == 'cntk':
        idx = package_name_list.index('cntk')
    elif framework == 'tensorflow':
        idx = package_name_list.index('tensorflow-gpu')
        package_name = 'tensorflow-gpu'        
    else:
        raise ValueError            
    framework_version = package_version_list[idx]

    del package_name_list
    del package_version_list

@ex.capture
def get_iterator(framework, data_type, data_options, progressbar):
    iterator = Iterator(data_type, **data_options)
    if progressbar:
        iterator = tqdm(iterator)
    return iterator

def wrap_tqdm(iterator):
    from tqdm import tqdm    
    it = iter(iterator)
    #for i in range(5):    
    #    yield next(it) 
    #yield from tqdm(iterator)

@ex.capture
def get_model(module, data_type, data_options, dnn_arch, rnn_layers, ngpu):
    if data_type == 'image':
        channel, xdim, ydim = data_options['image_shape']
        output_num = data_options['label_size']
        gpu_mode = True if ngpu >= 1 else False
        if dnn_arch == 'CNN':
            model = module.CNN(channel, xdim, ydim, output_num)
    elif data_type == "sequence":
        pass
    return model


@ex.capture
def _get_trainer(module, model, ngpu, trainer_options, data_options, time_options):
    trainer = module.Trainer(model, ngpu, trainer_options, data_options, time_options)
    return trainer


@ex.capture
def get_trainer(_config, framework, framework_version, ngpu):
    model = None
    if framework == 'torch':
        module = import_module('benchmark.models.th') 
        model = get_model(module=module)
        trainer = _get_trainer(module=module, model=model)
    elif framework == 'mxnet':
        module = import_module('benchmark.models.mx')
        model = get_model(module=module)
        trainer = _get_trainer(module=module, model=model)        
    elif framework == 'chainer':
        module = import_module('benchmark.models.ch')
        model = get_model(module=module)        
        trainer = _get_trainer(module=module, model=model)
    elif framework == 'cntk':
        module = import_module('benchmark.models.ct')
        model = get_model(module=module)        
        trainer = _get_trainer(module=module, model=model)        
    elif framework == 'tensorflow':
        module = import_module('benchmark.models.th')
        model = get_model(module=module)
        trainer = _get_trainer(module=module, model=model)        
    else:
        raise ValueError

    return trainer


@ex.capture
def train(trainer, iterator, opt_type, opt_conf):
    np.random.seed(1)
    trainer.set_optimizer(opt_type, opt_conf)            
    results = trainer.run(iterator)
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
