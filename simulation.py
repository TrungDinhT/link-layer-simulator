import numpy as np
from ABP import SimulatorABP, SimulatorABP_NAK
from GBN import SimulatorGBN
from baseclasses import StatsManager, Protocol


def simulate(protocol):
    
    # Input parameters
    H = 432 # bits = 54 bytes
    l = 12000 # bits = 1500 bytes
    delta_rate = np.array([2.5, 5, 7.5, 10, 12.5]) # delta_rate*tau = delta = timeout
    C = 5000000 # 5MB/s
    taus = np.array([0.01, 0.5]) / 2 # seconds
    BERs = np.array([0, 1e-4, 1e-5])
    duration = 10000

    # Init statistic manager and simulator
    statsManager = StatsManager(protocol, delta_rate, taus.shape[0]*BERs.shape[0])
    if protocol == Protocol.ABP:
        maxSN = 2
        simulator = SimulatorABP(H, l, C, maxSN, duration, statsManager)
    elif protocol == Protocol.ABP_NAK:
        maxSN = 2
        simulator = SimulatorABP_NAK(H, l, C, maxSN, duration, statsManager)
    elif protocol == Protocol.GBN:
        maxSN = 4
        simulator = SimulatorGBN(H, l, C, maxSN, duration, statsManager)
    else:
        print 'unknown protocol'
        exit(1)
    
    # Running simulation
    i = 0 # initial row index
    j = 1 # initial column index
    k = 0 # initial group index (we have 2 groups : tau = 0.01 and tau = 0.5)

    for tau in taus:
        for timeout in delta_rate*tau:
            for BER in BERs:
                statsManager.reset()
                simulator.set_params(timeout, tau, BER)
                simulator.run()
                statsManager.record_stats(i, j)
                j = j + 1
            i = i + 1
            j = k*BERs.shape[0] + 1 # reset column index
        i = 0 # reset row index
        k = k + 1 # increase group index
        j = k*BERs.shape[0] + 1 # reset column index

    statsManager.save_to_csv() 
