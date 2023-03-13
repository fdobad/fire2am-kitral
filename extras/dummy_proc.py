from time import sleep
from sys import stderr, stdout

def decorator(func):
    printer = func
    def wrapped(*args, **kwargs):
        if 'flush' in kwargs.keys():
            kwargs.pop('flush')
        printer(*args, **kwargs, flush=True)
    return wrapped

print = decorator(print)

print('Hello World')
for i in range(10):
    print('out ', i, file=stdout)
    print('err ', i, file=stderr)
    print('doing stuff', i)
    sleep(1)
print('Bye World', flush=True)

