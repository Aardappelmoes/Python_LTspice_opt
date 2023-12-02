
## Python optimizer for LTspice, Bob Adams, Fellow Emeritus, Analog Devices 2023 (C)
## optimizer will adjust selected schematic components (designated in the setup file function 'simControl')
## in an attempt to match the target response, set in the setup file function 'setTarget'

## Note, the schematic name is read from the simControl function
## which is imported from the setup python file (see line below)
## The setup file must be generated by the user for a particular LTspice schematic and sim
## See any of the example files in this distribution for an example
## Change the following line to point to your own setup file.

from example2_diff_setup import simControl, setTarget

# notes:

# the simControl function sets the following;
# ** paths to the LTspice executable
# ** working LTspice directory
# ** schematic instance names to be optimized
# ** min and max values of those instance
# ** tolerance of those instances
# ** match mode (amplitude only, phase only, or both)

# the setTarget function sets the target amplitude and/or phase response
# It is calculated at the same frequencies as used in
# the .ac spice control line in the schematic
# It also sets the error weights; if you want more precise matching in some frequency
# regions, you can increase the error weights in that frequency region


import numpy as np
import matplotlib.pyplot as plt
import os
import subprocess
import time
import sys
import hashlib

from PyLTSpice import RawRead # user must install into env from https://pypi.org/project/PyLTSpice/
from scipy.optimize import least_squares


print('******\n******\nCopyright (C) Robert Adams 2023\n******\n******')

# LTspice Optimizer
# Copyright (C) Robert Adams 2023

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.



plt.interactive(True)


# Initialize global variables
iterationCount = 0
# ******************************* functions ***************************

def optLTspice(optParams, *args, **kwargs): # this is the evaluation function called by sciPy least-squares
    global iterationCount

    netlist_fname = kwargs['netlist_fnameD']
    RunLTstring = kwargs['RUnLTstringD']
    LTspice_outputfile = kwargs['LTspice_outputfileD']
    LTspice_output_node = kwargs['LTspice_output_nodeD']
    matchMode = kwargs['matchModeD']
    target = kwargs['targetD']
    errWeights = kwargs['errWeightsD']
    numlines_netlist = kwargs['numlines_netlistD']
    netlist = kwargs['netlistD']
    nomParams = kwargs['nomParamsD']
    OptLine = kwargs['OptLineD']
    numOptd = kwargs['numOptdD']


    for k in range(numOptd):
        #netlist[OptLine[k]][3] = f'{optParams[k] * nomParams[k]:.12e}'
        netlist[OptLine[k]][3] = f'{nomParams[k]*np.exp(optParams[k]):.12e}'

    print('\ncurrent component values')

    for k in range(numOptd):
        #print(f'{netlist[OptLine[k]][0]} {optParams[k] * nomParams[k]:.12e}')
        print(f'{netlist[OptLine[k]][0]} {nomParams[k] * np.exp(optParams[k]):.12e}')

    with open(netlist_fname, 'w') as fid_wr_netlist:
        for k in range(numlines_netlist):
            thisLine = netlist[k]
            fid_wr_netlist.write(' '.join(thisLine) + '\n')

    time.sleep(0.1)


    # get hash of .raw file so we know when the spice sim is done
    # we assume this file already exists from the initial simulation
    # other wise we would need to create am empty file to start
    md5=hashlib.md5(open(LTspice_outputfile,'rb').read()).hexdigest()
    # Run the simulation.
    status = subprocess.call(RunLTstring, shell=True)
    md5_post = md5 # start by assuming its not done (hash hasnt changed)
    while md5_post == md5 : # sleep until the hash of the raw file changes
        time.sleep(0.2)
        md5_post=hashlib.md5(open(LTspice_outputfile,'rb').read()).hexdigest()

    # the following line seems to be effective at "blocking" execution until the previous
    # subprocess call has finished; even though subprocess.call is in theory blocking
    #Data = subprocess.check_output(['wmic', 'process', 'list', 'brief'])
    if status:
        print('ERROR, LTspice sim failed to run. Check setup')
        sys.exit()
    time.sleep(0.1)
    LTR = RawRead(LTspice_outputfile)
    #print(LTR.get_trace_names())
    #print(LTR.get_raw_property())
    outNode = LTR.get_trace(LTspice_output_node)
    fresp = np.abs(outNode)
    freqx = LTR.get_trace('frequency')
    freqx = np.abs(freqx)
    if matchMode == 2 or matchMode == 3:
        phase = np.unwrap(np.angle(outNode))

    if matchMode == 1:  # ampl only
        optCurrent = fresp
    if matchMode == 2:  # phase only
        optCurrent = phase
    if matchMode == 3:  # ampl and phase
        optCurrent = np.concatenate((fresp, phase))

    if len(target) != len(optCurrent):
        print('ERROR, something went wrong with the LTspice sim...')
        sys.exit()

    err = target - optCurrent  # error between target and current response

    err = err * errWeights  # apply frequency-dependent optimization
    print('\ncurrent rms error (weighted) =', np.sqrt(np.mean(err ** 2)))

    iterationCount += 1
    print('iteration count =', iterationCount)

    return err



# ******************

def runSim(LTspice_outputfile, RunLTstring) :
    # run an LTspice sim. Assumes netlist is already written.
    # this code will stall until the .raw file has been written
    # The LTspice sim time can be highly variable in cases where it's
    # difficult to find a DC operating point
    if(os.path.isfile(LTspice_outputfile)) :
        os.remove(LTspice_outputfile) # delete in case of previous pass
    # Create an empty raw file
    with open(LTspice_outputfile, 'w') as fp:
        pass
    # get hash of .raw file so we know when the spice sim is done
    md5=hashlib.md5(open(LTspice_outputfile,'rb').read()).hexdigest()
    # Run the simulation. First check to make sure LTspice is not running from last call
    status = subprocess.call(RunLTstring, shell=True) # run it
    md5_post = md5 # start by assuming its not done (hash hasnt changed)
    while md5_post == md5 : # sleep until the hash of the raw file changes
        time.sleep(0.2)
        md5_post=hashlib.md5(open(LTspice_outputfile,'rb').read()).hexdigest()
    if status:
        print('ERROR, LTspice sim failed to run. Check setup')
        sys.exit()
    time.sleep(0.2)

# **********************************************************
# reads in the original schematic and replaces the instance values
# with the optimized insatnce values
def update_schematic(pass2schem, simControlDict):

    numOptd = pass2schem['numOptdD']
    OptLine = pass2schem['OptLineD']
    nomParams = pass2schem['nomParamsD']
    netlist = pass2schem['netlistD']
    filePath = pass2schem['filePathD']
    fileName = pass2schem['fileNameD']
    X = pass2schem['XD']
    simctrlInstTol = simControlDict['simControlInstTolD']
    simctrlOptInstNames = simControlDict['simControlOPtInstNamesD']

    # Read in schematic to update
    schem_fname = os.path.join(filePath, fileName + '.asc')
    with open(schem_fname, 'r') as file:
        schem = file.readlines()

    changeNext = False
    roundStringNext = 'E96'
    new_schem = []

    for line in schem:
        line = line.strip().split()

        if changeNext:
            newVal = round63(instValNext, roundStringNext)
            newVal = newVal[0].astype('float') # change from type ndarray to single float

            line[2] = f'{newVal:.3e}'
            print(f'Inst, opt val, quantized val = {instNm} {instValNext} {newVal:.3e}')
            changeNext = False

        if line[1] == 'InstName':
            instNm = line[2]
            changeNext = False
            for kk in range(numOptd):
                if netlist[OptLine[kk]][0] == instNm:
                    # Find the index to this instance in simctrlOptInstNames
                    # so that we know which tolerance to use
                    xx = simctrlOptInstNames.index(instNm)
                    # Next line has the value to change
                    changeNext = True
                    #instValNext = X[kk] * nomParams[kk]
                    instValNext = nomParams[kk] * np.exp(X[kk])

                    roundStringNext = simctrlInstTol[xx]

        new_schem.append(' '.join(line) + '\n')

    # Write new schem file
    schem_fname = os.path.join(filePath, fileName + '_opt.asc')
    with open(schem_fname, 'w') as file:
        file.writelines(new_schem)

# **********************************************************
# function to round component values to tolerance defined by "E-series"
# (c) 2014-2022 Stephen Cobeldick, converted from Matlab distribution


def round63(X, ser, rnd=None):
    # Constants for E-Series
    E_SERIES = {
        'E3': np.array([100, 220, 470]), # 40% tol
        'E6': np.array([100, 150, 220, 330, 470, 680]), # 20% tol
        'E12': np.array([100, 120, 150, 180, 220, 270, 330, 390, 470, 560, 680, 820]), #10%
        'E24': np.array([ # 5% tol
            100, 110, 120, 130, 150, 160, 180, 200, 220, 240, 270, 300,
            330, 360, 390, 430, 470, 510, 560, 620, 680, 750, 820, 910
        ]),
        'E48': np.array([ # 2% tol
            100, 105, 110, 115, 121, 127, 133, 140, 147, 154, 162, 169,
            178, 187, 196, 205, 215, 226, 237, 249, 261, 274, 287, 301,
            316, 332, 348, 365, 383, 402, 422, 442, 464, 487, 511, 536,
            562, 590, 619, 649, 681, 715, 750, 787, 825, 866, 909, 953
        ]),
        'E96': np.array([ # 1% tol
            100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
            133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
            178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
            237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
            316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
            422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
            562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
            750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976
        ]),
        'E192': np.array([ # 1/2 % tolerance
            100, 101, 102, 104, 105, 106, 107, 109, 110, 111, 113, 114,
            115, 117, 118, 120, 121, 123, 124, 126, 127, 129, 130, 132,
            133, 135, 137, 138, 140, 142, 143, 145, 147, 149, 150, 152,
            154, 156, 158, 160, 162, 164, 165, 167, 169, 172, 174, 176,
            178, 180, 182, 184, 187, 189, 191, 193, 196, 198, 200, 203,
            205, 208, 210, 213, 215, 218, 221, 223, 226, 229, 232, 234,
            237, 240, 243, 246, 249, 252, 255, 258, 261, 264, 267, 271,
            274, 277, 280, 284, 287, 291, 294, 298, 301, 305, 309, 312,
            316, 320, 324, 328, 332, 336, 340, 344, 348, 352, 357, 361,
            365, 370, 374, 379, 383, 388, 392, 397, 402, 407, 412, 417,
            422, 427, 432, 437, 442, 448, 453, 459, 464, 470, 475, 481,
            487, 493, 499, 505, 511, 517, 523, 530, 536, 542, 549, 556,
            562, 569, 576, 583, 590, 597, 604, 612, 619, 626, 634, 642,
            649, 657, 665, 673, 681, 690, 698, 706, 715, 723, 732, 741,
            750, 759, 768, 777, 787, 796, 806, 816, 825, 835, 845, 856,
            866, 876, 887, 898, 909, 920, 931, 942, 953, 965, 976, 988
        ])
    }

    def r63ss2c(arr):
        if isinstance(arr, str) and len(arr) == 1:
            return arr
        return arr

    def round_to_series(x, series):
        return series[np.argmin(np.abs(x - series))]

    if rnd is None:
        #rnd = 'harmonic'
        rnd = 'arithmetic'

    rnd = r63ss2c(rnd).lower()

    if ser not in E_SERIES:
        raise ValueError(f'Series "{ser}" is not supported.')

    ns = E_SERIES[ser]
    pwr = np.log10(X)
    idr = np.isfinite(pwr) & np.isreal(pwr)

    if not np.any(idr):
        return np.full_like(X, np.nan)

    # Determine the order of PNS magnitude required
    omn = np.floor(np.min(pwr[idr])) # -4 debug
    omx = np.ceil(np.max(pwr[idr])) # -3 debug

    # Extrapolate the PNS vector to cover all input values
    temp = 10.0 ** np.arange(omn - 3, omx-1)
    temp = temp.reshape((-1,1)) # make 2D row vect
    temp = temp.T # transpose, change shape from 4x1 to 1x4
    ns = ns.reshape((-1,1)) # make 2d row vect

    pns = ns * temp

    # now we need to flatten
    pns = pns.flatten(order = 'F')
    # Generate bin edge values
    if rnd == 'harmonic':
        edg = 2 * pns[:-1] * pns[1:] / (pns[:-1] + pns[1:])
    elif rnd == 'arithmetic':
        edg = (pns[:-1] + pns[1:]) / 2
    elif rnd == 'up':
        edg = pns[:-1]
    elif rnd == 'down':
        edg = pns[1:]
    else:
        raise ValueError(f'Rounding method "{rnd}" is not supported.')

    # Place values of X into PNS bins
    idx = np.digitize(X[idr], edg)
    idx[idx == 0] = 1  # Handle values below the smallest bin edge

    # Use the bin indices to select output values from the PNS
    Y = pns[idx - 0]

    return Y



# *********************************************************
# ************************** Main *************************
# *********************************************************

def main():

    passCellDict = {}
    simControlDict = {}
    simControlDict = simControl()  # Read simulation control input file, filled out by user

    fileName = simControlDict['fileNameD']
    spicePath = simControlDict['spicePathD']
    filePath = simControlDict['filePathD']
    simControlOPtInstNames = simControlDict['simControlOPtInstNamesD']
    simControlMinVals = simControlDict['simControlMinValsD']
    simControlMaxVals = simControlDict['simControlMaxValsD']
    simControlInstTol= simControlDict['simControlInstTolD']
    LTspice_output_node = simControlDict['LTSPice_output_nodeD']
    matchMode = simControlDict['matchModeD']

    # Derived file paths and run scripts
    netlist_fname = f'{filePath}{fileName}.net'  # Netlist filename
    LTspice_outputfile = f'{filePath}{fileName}.raw'  # sim results filename
    RunLTstring = f'start "LTspice" "{spicePath}" -b "{filePath}{fileName}.net"'

    passCellDict['spicePathD'] = spicePath
    passCellDict['filePathD'] = filePath
    passCellDict['fileNameD'] = fileName
    passCellDict['filePathD'] = filePath
    passCellDict['netlist_fnameD'] = netlist_fname
    passCellDict['RUnLTstringD'] = RunLTstring
    passCellDict['LTspice_outputfileD'] = LTspice_outputfile
    passCellDict['LTspice_output_nodeD'] = LTspice_output_node
    passCellDict['matchModeD'] = matchMode


    # Send command to write netlist
    string = f'start "LTspice" "{spicePath}" -netlist "{filePath}{fileName}.asc"'
    print(f'Issuing command to write LTspice netlist\n{string}')
    status = subprocess.call(string, shell=True)
    time.sleep(0.2) # in theory, subprocess.call is 'blocking', but it doesn't always work, so...


    # Read in the initial netlist. This will be held in memory and modified for every
    # pass through the least-squares. Inside the least-squares function
    # the netlist will be written to a file for each pass, so that LTspice can run
    with open(netlist_fname, 'r') as fid:
        netlist = fid.readlines()

    netlist = [line.strip().split() for line in netlist]  # Split lines into words
    numlines_netlist = len(netlist)


    passCellDict['netlistD'] = netlist
    passCellDict['numlines_netlistD'] = numlines_netlist

    # Find how many components are being optimized and make an index that points
    # to the line number in the netlist of those components
    # this makes the least-squares evaluation function faster because it doesn't
    # need to search through the entire netlist each time
    numOptd = len(simControlOPtInstNames)  # Number of instances being optimized
    OptLine = [0] * numOptd  # An array that points to the netlist lines with the instance names to be optimized


    kkk = 1
    OptLine = [0] * numOptd  # Initialize the OptLine array
    UB = [0.0] * numOptd  # Initialize the upper bound array
    LB = [0.0] * numOptd  # Initialize the lower bound array

    for kk in range(numOptd):  # search all opt instance names to see if they are on the kth netlist line
        for k in range(numlines_netlist):  # Go through all netlist lines to look for this instance
            thisLine = netlist[k]
            if simControlOPtInstNames[kk] in thisLine[0]:
                #print('found ',simControlOPtInstNames[kk], 'in line ', k, 'with kk= ',kk)
                OptLine[kkk - 1] = k
                UB[kkk - 1] = float(simControlMaxVals[kk])  # Upper bound to pass to optimizer
                LB[kkk - 1] = float(simControlMinVals[kk])  # Lower bound to pass to optimizer
                kkk += 1

    numMatchingInstFound = kkk - 1

    if numOptd != numMatchingInstFound:
        print('ERROR;')
        print(f'number of instances to be optimized in control file = {numOptd}')
        print(f'number of matching instances found in netlist = {numMatchingInstFound}')
        print('check Instance name spelling in control file')
        sys.exit()

    passCellDict['numOptdD'] = numOptd
    passCellDict['OptLineD'] = OptLine
    nomParams = [0.0] * numOptd
    # This holds the nominal values, initialized to schematic values

    for k in range(numOptd):
        thisLine = netlist[OptLine[k]]  # Only lines that will be optimized here
        newStr = thisLine[3]  # Assuming value is the 4th entry (inst, node, node, value)

        # Replace any 'micro' symbols from LTspice with 'u'
        newStr = newStr.replace(chr(181), 'u')  # Replace micro symbol with 'u'

        if not newStr.isnumeric():  # If it's not a number, handle symbols like k, M, pf, etc.
            newStr = newStr.replace('M', 'e6')
            newStr = newStr.replace('G', 'e9')
            newStr = newStr.lower()
            newStr = newStr.replace('k', 'e3')
            newStr = newStr.replace('pf', 'e-12')
            newStr = newStr.replace('ph', 'e-12')
            newStr = newStr.replace('p', 'e-12')
            newStr = newStr.replace('nf', 'e-9')
            newStr = newStr.replace('nh', 'e-9')
            newStr = newStr.replace('n', 'e-9')
            newStr = newStr.replace('uf', 'e-6')
            newStr = newStr.replace('uh', 'e-6')
            newStr = newStr.replace('u', 'e-6')
            newStr = newStr.replace('mf', 'e-3')
            newStr = newStr.replace('mh', 'e-3')
            newStr = newStr.replace('m', 'e-3')

        nomParams[k] = float(newStr)  # Convert the modified value to float

    passCellDict['nomParamsD'] = nomParams

    print('\n*** setup file info, please check ***\n')
    print('inst name, init value, Min, Max, Tolerance ***\n')
    for k in range(numOptd):
        print(f'{netlist[OptLine[k]][0]} {nomParams[k]:.12e} {LB[k]} {UB[k]} {simControlInstTol[k]}')

    print('\nLTspice output node from setup file = ',LTspice_output_node,'\n')
    print('LTspice run command = ',RunLTstring,'\n')
    if matchMode == 1:
        print('Match mode = Amplitude Only\n')
    if matchMode == 2:
        print('Match mode = Phase Only\n')
    if matchMode == 3:
        print('Match mode = Amplitude + Phase\n')



    x = input('Check accuracy above, enter C to continue or any other key to exit ')
    if x.lower() != 'c':
        sys.exit()


    # Run initial simulation to get frequencies
    print(f'Issuing command to run initial LTspice simulation\n{RunLTstring}')

    runSim(LTspice_outputfile,RunLTstring)
    
    # read the .raw sim results
    LTR = RawRead(LTspice_outputfile)
    outNode = LTR.get_trace(LTspice_output_node)
    fresp = np.abs(outNode)
    if matchMode == 2 or matchMode == 3: # only compute phase if you are going to use it
        phase = np.unwrap(np.angle(outNode))
    freqx = LTR.get_trace('frequency')
    freqx = np.abs(freqx)
    numFreqs = len(freqx)

 
    # now that we have the freqs from the initial sim, we can get
    # the target response from the user-defined setup file

    [target,errWeights] = setTarget(freqx, matchMode)

    passCellDict['targetD'] = target
    passCellDict['errWeightsD'] = errWeights
    if matchMode==3: # target is concatenation of ampl and phase, seperate out for plotting
        target_fresp = target[0:numFreqs]
        errWeights_fresp = errWeights[0:numFreqs]
        target_phase = target[numFreqs:]
        errWeights_phase = errWeights[numFreqs:]

    # plot the results of the initial sim on top of the target response, as well as the error weights

    if matchMode == 1:  # Ampl only match
        fig, axs = plt.subplots(2)
        axs[0].semilogx(freqx, 20 * np.log10(fresp),label='init sim')
        axs[0].semilogx(freqx,20 * np.log10(target),label='target')
        axs[0].legend()
        axs[0].set_ylabel('dB')
        axs[1].semilogx(freqx,errWeights,label='error weights')
        axs[1].legend()
        fig.canvas.draw_idle()
        fig.canvas.flush_events()

    if matchMode == 2:  # Phase only match
        fig, axs = plt.subplots(2)
        axs[0].semilogx(freqx, phase,label='init sim phase')
        axs[0].semilogx(freqx,target,label='target phase')
        axs[0].legend()
        axs[0].set_ylabel('radians')
        axs[1].semilogx(freqx,errWeights,label='error weights')
        axs[1].legend()
        fig.canvas.draw_idle()
        fig.canvas.flush_events()

    if matchMode == 3:  # Both phase and ampl match
        fig, axs = plt.subplots(2)
        axs[0].semilogx(freqx, 20 * np.log10(fresp),label='init sim fresp')
        axs[0].semilogx(freqx,20 * np.log10(target_fresp),label='target fresp')
        axs[0].legend()
        axs[0].set_ylabel('dB')
        axs[1].semilogx(freqx,errWeights_fresp,label='error weights for ampl')
        axs[1].legend()
        fig.canvas.draw_idle()
        fig.canvas.flush_events()


    x = input('Check initial sim and target plots, enter C to continue or any other key to exit ')
    if x.lower() != 'c':
        sys.exit()
        




    print('\n****************\n**************\nEntering Optimization Loop, please be patient ...\n************\n***********\n')

    #UB = [ub / nom for ub, nom in zip(UB, nomParams)]  # Translate upper bounds into relative upper bounds
    #LB = [lb / nom for lb, nom in zip(LB, nomParams)]  # Translate lower bounds into relative lower bounds
    # val = nom_val*exp(X), log(val)=X+log(nom_val), X = log(val)-log(nom_val), Xmax=log(val_max)-log(nom_val)
    # Xmin = log(val_min)-log(nom_val)
    for k in range(numOptd):
        UB[k] = np.log(UB[k]) - np.log(nomParams[k])
        LB[k] = np.log(LB[k]) - np.log(nomParams[k])

    #optParams = np.ones(numOptd)
    optParams = np.zeros(numOptd) # start at 0 for ratiometric, because e^0 = 1
    # note the starting values are all 0's. The actual component values
    # are current_Val=starting_Val*exp(X) where X is the optimizer variable.

    # run least-squares, step size is set to 0.1% to make sure
    # that the ltspice sim actually can see a difference when the components are wiggled
    #maxEvals = np.floor(700 / numOptd) # max 700 times through the error calc fun

    X = least_squares(optLTspice, optParams,method = 'trf',bounds=(LB, UB),diff_step=1e-5, ftol=1e-5,kwargs=passCellDict).x  # Optimize using least_squares function

    passCellDict['XD']=X



    print('\n*************\n************\nDONE! Generating outputs ...\n***********\n*********\n')
    for k in range(numOptd):
        #print(f'{netlist[OptLine[k]][0]} {X[k] * nomParams[k]:2.12e}')
        print(f'{netlist[OptLine[k]][0]} {nomParams[k] * np.exp(X[k]):2.12e}')

    time.sleep(0.1)
    # Re-run simulation with current netlist
    print(f'Issuing command to run post-opt LTspice simulation\n{RunLTstring}')

    runSim(LTspice_outputfile,RunLTstring)
    print(f'Done simulation, plotting\n')
    time.sleep(1)
    LTR = RawRead(LTspice_outputfile)
    outNode = LTR.get_trace(LTspice_output_node)
    fresp_opt = np.abs(outNode)
    if matchMode == 2 or matchMode == 3:
        phase_opt = np.unwrap(np.angle(outNode))

    # plot opt results before schematic generation/component quantization
    if matchMode == 1:
        fig, ax = plt.subplots()
        #plt.figure()
        ax.semilogx(freqx, 20 * np.log10(target), 'g',label='target')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt), 'r',label='opt')
        fig.canvas.draw()
        fig.canvas.flush_events()
        plt.title('Ampl Response Opt results vs target ')
        plt.legend()
        plt.ylabel("dB")
        plt.xlabel("freq")
        fig.canvas.draw()
        fig.canvas.flush_events()



    if matchMode == 2:  # Phase only
        fig, ax = plt.subplots()
        ax.semilogx(freqx, target, 'g',label='target')
        ax.semilogx(freqx, phase_opt, 'r',label='opt')
        plt.title('Phase Opt results vs target')
        plt.legend()
        plt.ylabel("radians")
        fig.canvas.draw()
        fig.canvas.flush_events()


    if matchMode == 3:  # Phase and ampl
        fig, ax = plt.subplots()
        ax.semilogx(freqx, 20 * np.log10(target_fresp), 'g',label='target')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt), 'r',label='opt')
        plt.title('Ampl Response Opt results vs target')
        plt.legend()
        plt.ylabel("dB")
        fig.canvas.draw()
        fig.canvas.flush_events()

        fig, ax = plt.subplots()
        ax.semilogx(freqx, target_phase, 'g',label='target')
        ax.semilogx(freqx, phase_opt, 'r',label='opt')
        plt.title('Phase Opt results vs target')
        plt.legend()
        plt.ylabel("radians")
        fig.canvas.draw()
        fig.canvas.flush_events()

    

    # generate a new schematic with '_opt' appended to name, with the optimized values
    # Note the optimized values are quantized based on the user "E-series" inputs.
    # This is currently outside the optimization loop. If you need better performance
    # I suggest you take the worst-tolerance components and remove them from the
    # list of instances to be optimized, and then re-run the optimizer based on the
    # new '_opt' schematic. 
    update_schematic(passCellDict, simControlDict)  # Write a new _opt schematic (Quantization applied on write-out)
    time.sleep(0.1)
    print(f'\n\nNew schematic with optimum component values generated\nFilename = {filePath}{fileName}_opt.asc\n\n')

    # Re-run simulation on the "_opt" schematic to check the quantization
    # Send command to write netlist
    string = f'"{spicePath}" -netlist "{filePath}{fileName}_opt.asc"'
    print(f'\nIssuing command to write new netlist from optimized schematic\n{string}')
    status = subprocess.call(string, shell=True)
    time.sleep(0.1)

    RunLTstring_opt = f'"{spicePath}" -b "{filePath}{fileName}_opt.net"'
    LTspice_outputfile_opt = f'{filePath}{fileName}_opt.raw'

    # Run sim on _Opt schematic

    print(f'\nIssuing command to run post-opt LTspice simulation w quant values\n{RunLTstring_opt}')
    
    runSim(LTspice_outputfile_opt,RunLTstring_opt)

    LTR = RawRead(LTspice_outputfile_opt)
    outNode = LTR.get_trace(LTspice_output_node)
    fresp_opt_quant = np.abs(outNode)
   
    if matchMode == 2 or matchMode == 3:
        phase_opt_quant = np.unwrap(np.angle(outNode))
    

    # Plot the target, optimized, and quantized (from new schem) optimized responses
    if matchMode == 1:
        fig, ax = plt.subplots()
        ax.semilogx(freqx, 20 * np.log10(target), 'g',label='target')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt), 'r',label='opt')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt_quant), 'b',label='opt quant')
        plt.title('Ampl Resp Opt results from sim of new schematic')
        plt.legend()
        plt.ylabel("dB")
        fig.canvas.draw()
        fig.canvas.flush_events()


    if matchMode == 2:  # Phase only
        fig, ax = plt.subplots()
        ax.semilogx(freqx, target, 'g',label='target')
        ax.semilogx(freqx, phase_opt, 'r',label='opt')
        ax.semilogx(freqx, phase_opt_quant, 'b',label='opt quant')
        plt.title('Phase Opt results from sim of new schematic')
        plt.legend()
        plt.ylabel("radians")
        fig.canvas.draw()
        fig.canvas.flush_events()


    if matchMode == 3:  # Phase and ampl
        fig, ax = plt.subplots()
        ax.semilogx(freqx, 20 * np.log10(target_fresp), 'g',label='target')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt), 'r',label='opt')
        ax.semilogx(freqx, 20 * np.log10(fresp_opt_quant), 'b',label='opt quant')
        plt.title('Ampl Resp Quantized Opt results from sim of new schematic')
        plt.legend()
        plt.ylabel("dB")
        fig.canvas.draw()
        fig.canvas.flush_events()

        fig, ax = plt.subplots()
        ax.semilogx(freqx, target_phase, 'g')
        ax.semilogx(freqx, phase_opt, 'r')
        ax.semilogx(freqx, phase_opt_quant, 'b')
        plt.title('Phase Resp Quantized Opt results from sim of new schematic')
        plt.legend(['target', 'opt', 'opt quant'])
        plt.ylabel("radians")
        fig.canvas.draw()
        fig.canvas.flush_events()

    print('\n*******\n***** DONE! ******\n*******')
    sys.exit()

if __name__ == "__main__":
    main()