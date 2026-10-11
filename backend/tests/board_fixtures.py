def element(id, type='rectangle', version=1, **overrides):
    """A minimal Excalidraw element as the editor saves it."""
    base = {'id': id, 'type': type, 'version': version, 'versionNonce': 7, 'isDeleted': False,
            'x': 10, 'y': 20, 'width': 100, 'height': 50, 'angle': 0,
            'strokeColor': '#1e1e1e', 'backgroundColor': 'transparent', 'fillStyle': 'solid', 'strokeWidth': 2,
            'strokeStyle': 'solid', 'roughness': 1, 'opacity': 100, 'groupIds': [], 'frameId': None,
            'roundness': None, 'seed': 1, 'boundElements': None, 'updated': 1, 'link': None, 'locked': False, 'index': 'a0'}
    if type in ('arrow', 'line', 'freedraw'):
        base['points'] = [[0, 0], [100, 50]]
    if type == 'text':
        base.update(text='Label', originalText='Label', containerId=None, fontSize=20, fontFamily=5)
    base.update(overrides)
    return {'id': id, 'version': base['version'], 'element': base}
