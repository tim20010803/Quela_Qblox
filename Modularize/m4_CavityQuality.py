import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from Modularize.m2_CavitySpec import Cavity_spec
from Modularize.support import Data_manager, QDmanager
from Modularize.support.UserFriend import *
from quantify_core.measurement.control import MeasurementControl
from Modularize.support.Path_Book import find_latest_QD_pkl_for_dr
from Modularize.support import init_meas, init_system_atte, shut_down

def qualityFit_executor(QD_agent:QDmanager,meas_ctrl:MeasurementControl,ro_amp:float,specific_qubits:str,ro_span_Hz:float=10e6,run:bool=True,f_shifter:float=0):
    rof = {str(specific_qubits):QD_agent.quantum_device.get_element(specific_qubits).clock_freqs.readout()+f_shifter}
    
    if run:
        qb_CSresults = Cavity_spec(QD_agent,meas_ctrl,ro_bare_guess=rof,ro_amp=ro_amp,q=specific_qubits,ro_span_Hz=ro_span_Hz,run=True)[specific_qubits]
    else:
        qb_CSresults = Cavity_spec(QD_agent,meas_ctrl,ro_bare_guess=rof,ro_amp=ro_amp,q=specific_qubits,ro_span_Hz=ro_span_Hz,run=False)[specific_qubits]
    
    QD_agent.quantum_device.get_element(specific_qubits).clock_freqs.readout(rof[specific_qubits]-f_shifter)

    return qb_CSresults

def show_quality_for(CS_results:dict,target_q:str)->dict:
    qi = round(CS_results[target_q].quantities_of_interest['Qi'].nominal_value*1e-3,2) # in k
    ql = round(CS_results[target_q].quantities_of_interest['Ql'].nominal_value*1e-3,2)
    qc = round(CS_results[target_q].quantities_of_interest['Qc'].nominal_value*1e-3,2)

    print(f"{target_q}: Qi= {qi}k, Qc= {qc}k, Ql= {ql}k")
    return {"QI":qi,"QC":qc,"QL":ql}

if __name__ == "__main__":

    """ Fill in """
    execution = True

    sweetSpot = True
    DRandIP = {"dr":"drke","last_ip":"116"}
    ro_elements = {
        "q0":{"ro_amp":0.7,"ro_atte":50}
    }
    freq_shift = 10e6


    """ Preparations """ 
    QD_path = find_latest_QD_pkl_for_dr(which_dr=DRandIP["dr"],ip_label=DRandIP["last_ip"])
    QD_agent, cluster, meas_ctrl, ic, Fctrl = init_meas(QuantumDevice_path=QD_path,mode='l')


    """ Running """
    CS_results = {}
    for qubit in ro_elements:
        if ro_elements[qubit]["ro_atte"] != '':
            QD_agent.Notewriter.save_DigiAtte_For(ro_elements[qubit]["ro_atte"],qubit,'ro')
        if sweetSpot:
            Fctrl[qubit](QD_agent.Fluxmanager.get_sweetBiasFor(target_q=qubit))
        else:
            Fctrl[qubit](0)
        init_system_atte(QD_agent.quantum_device,[qubit],ro_out_att=QD_agent.Notewriter.get_DigiAtteFor(qubit,'ro'))
        CS_results[qubit] = qualityFit_executor(QD_agent=QD_agent,meas_ctrl=meas_ctrl,specific_qubits=qubit,ro_amp=ro_elements[qubit]["ro_amp"],run = execution, f_shifter=freq_shift,ro_span_Hz=10e6)
        Fctrl[qubit](0)
        cluster.reset()
        highlight_print(f"{qubit}: Cavity @ {round(CS_results[qubit].quantities_of_interest['fr'].nominal_value*1e-9,5)} GHz")
        _ = show_quality_for(CS_results,qubit)

    """ Storing (future) """


    """ Close """
    print('Cavity quality fit done!')
    shut_down(cluster,Fctrl)
