import os

# Data Proceing libraries

import numpy as np
import pandas as pd
import data_preparation as dp

# Interpol Libraries

import interpolation as ip
import skgstat as skg
import scipy


# Deep Learning Libraries

import tensorflow as tf
import deepkriging as dk
import tensorflow as tf
from keras.models import Sequential
from keras.layers import Dense, Dropout, BatchNormalization
import basemodel as bm

# Plotting Libraries

import matplotlib.pyplot as plt
import seaborn as sns
import ploting_utils as pu


def mae(y_true, y_pred):
    return np.mean(np.abs(y_true - y_pred).dropna())

def mse(y_true, y_pred):
    return np.mean(np.square((y_true - y_pred).dropna()))

def main():
    
    
    
    wholeMap = pd.read_csv('WholeMap_Rounds_40_to_17.csv')
    
    if reduceResolution:
        
        wholeMap = wholeMap.iloc[::12,:]
        
    Map, StackedMap = dp.prepare_map(wholeMap.copy(), length=length)
    
       
        
    known_points, unknown_points = dp.resample(StackedMap.copy(), sampling_distance_x, sampling_distance_y)
    
    
    if random:
        
        """
         If random, then the unknown points are randomly selected from the stacked map.
         The unknown points remain the same
         The amount of known points should match the amount of known points in uniform resampling
        """
        
        
        known_points = dp.randomsampling(StackedMap.copy(), len(known_points))
    
    if interpolate_whole_map:
            
        unknown_points = StackedMap
        
        
        
    # Interpolation
    
    ## Linear Grid Interpolation
    
    
    ResutLinearInterpolation = ip.grid_interpolation(known_points.copy(), unknown_points.copy(), method='linear', verbose=verbose)
    
    ## Kriging 
    
    
    ResultKriging = ip.kriging_skg(known_points.copy(), unknown_points.copy(), 10 )
    
                        
    # Deep Learning
        
    ## Preparing Deep Kriging Data
    
    
    StackedMapNormalizedForDK, known_pointsDK, unknown_pointsDK, maxvalsDK, minvalsDK = dk.normalize_data(StackedMap.copy(), known_points.copy(), unknown_points.copy()) # minmax normalize the data
    
    N = len(known_points) + len(unknown_points) # Calculate the number of points
    H = dk.calc_H_for_num_basis(len(StackedMap)) # Calculate the number of basis functions
    
    numBasis = dk.findWorkingNumBasis(len(202133),H,verbose=True) # Calculate the number of basis functions
            
        
    x_trainDK = dk.wendlandkernel(known_pointsDK[['x','y']], numBasis)
    np.save('x_trainDK.npy', x_trainDK.to_numpy())
    print('finished x train')
    x_valDK = dk.wendlandkernel(unknown_pointsDK[['x','y']], numBasis)
    np.save('x_valDK.npy', x_valDK.to_numpy())
    print(' finished x val')
    y_trainDK = known_points[['z']]
    np.save('y_trainDK.npy', y_trainDK.to_numpy())
    y_valDK = unknown_points[['z']]
    np.save('y_valDK.npy', y_valDK.to_numpy())
    
    DeepKrigingModel = dk.build_model(x_trainDK.shape[1], verbose=verbose)
    
    DeepKrigingModel, trainedModelPathDK = dk.train_model(DeepKrigingModel, x_trainDK, y_trainDK, x_valDK, y_valDK, scenario, epochs, save_hist=save_hist, verbose=verbose)
    
    DeepKrigingPrediction = dk.predict(trainedModelPathDK, x_valDK)[:,0]
    
    ResultDeepKriging = dk.reminmax(DeepKrigingPrediction, minvalsDK['z'], maxvalsDK['z'])
    
    ### Transform Deep Kriging Result into a pandas DataFrame with cols x, y, z
               
             
    DeepKrigingPrediction= pd.DataFrame([DeepKrigingPrediction,unknown_points['x'].to_numpy(),unknown_points['y'].to_numpy()]).transpose() # create a DataFrame 
                        
    DeepKrigingPrediction.columns = ['z','x','y'] # Fix column names
    
    DeepKrigingPrediction  = DeepKrigingPrediction[['x','y','z']]
    
    DeepKrigingPrediction.index = unknown_points.index # Fix index
    
    
    ## Base Model                       
        
    BaseModel = bm.build_model(verbose=verbose)
   
    BaseModel, trainedModelPathBase = bm.train(known_points[['x', 'y']], known_points[['z']], unknown_points[['x','y']], unknown_points['z'],BaseModel, epochs, scenario,save_hist=save_hist, verbose=verbose)

    ResultBaseModel =  bm.predict(trainedModelPathBase, unknown_points[['x','y']])
    
    
    
    
    #
    
    data = {'Linear Interpolation':ResutLinearInterpolation,'Kriging':ResultKriging,'Deep Kriging':DeepKrigingPrediction,'Base Model':ResultBaseModel}
    path = f'/home/schmijul/source/repos/thesis/newplots/main/{scenario}/'
    if not os.path.exists(path):
            os.makedirs(path)
                    
    
    # calculate errors
    
    maes = {}
    mses = {}
    
    keys = list(data.keys())
    for key in keys:
        
        maes[key] = mae(unknown_points['z'],data[key]['z'])
        mses[key] = mse(unknown_points['z'],data[key]['z'])
    
    
    f= open(f"{path}/error.txt","a+")
    f.write(f"{len(known_points)} known points, {len(unknown_points)} unknown points\n")
    f.write('\n')
    f.write(f"{scenario}\n")
    f.write('\n')
    f.write('\n')
    
    f.write('MAEs: \n')
    for key, value in maes.items(): 

        f.write('%s:%s\n' % (key, value))

    f.write('\n')
    #f.write(f"{maes}\n")
    
    f.write('MSES: \n')
    
    for key, value in mses.items(): 

        f.write('%s:%s\n' % (key, value))

    f.write('\n')
    #f.write(f"{mses}\n")
    
    
    # Plots
    
    
  
    for key in keys:
        
        pu.generateHeatMaps({key:data[key]},StackedMap, known_points, unknown_points, path +f'{key}.png')
        
        
    pu.generateHeatMaps(data,StackedMap, known_points,unknown_points, path+'heatmaps.png')
    


if __name__ == "__main__":
    
    # Genereal Params for execution
    
    
    verbose = 1
    epochs = 3000
    
    start_point=0
    length = None
    interpolate_whole_map = 0
    save_hist = 0
    reduceResolution = 0
    # Load data
    
    for interpolate_whole_map in [0,1]:
        for sampling_distance_x in [20, 18, 16, 14, 12, 10, 8, 6, 4, 2, ]: 
            
            sampling_distance_y = sampling_distance_x * 12
        
            # Name scenario ( for saving directories)
            
            for random in [False, True]:
            
                if random:
                    
                    scenario = f'wholeMap_x-{sampling_distance_x}_y-{int(sampling_distance_y/12)}_RandomSampling'
                    
                else:
                    
                    scenario = f'wholeMap_x-{sampling_distance_x}_y-{int(sampling_distance_y/12)}_UniformSampling'
                    
                    
                if interpolate_whole_map:
                    scenario = scenario + '_InterpolateAllPoints'
                main()
            
    
    print('fin')