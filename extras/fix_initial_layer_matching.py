#!/bin/env python3
"""
Match layers to layerWidgets    
"""
import re
layerComboBox = ['fuels','elevation','cbd','cbf']
layer_names = ['Fuels','mdt']
for lcb in layerComboBox:
    if lcb == 'fuels':
        regex = re.compile('model.*asc|[Ff]uel')
    for n in layer_names:
        if a:=re.match(regex,n):
            print(a.string)
            break
    else:
        print('set to none')
