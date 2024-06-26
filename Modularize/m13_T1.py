import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from qblox_instruments import Cluster
from numpy import mean, array, arange, std
from utils.tutorial_utils import show_args
from Modularize.support.UserFriend import *
from qcodes.parameters import ManualParameter
from Modularize.support import QDmanager, Data_manager
from quantify_scheduler.gettables import ScheduleGettable
from quantify_core.measurement.control import MeasurementControl
from Modularize.support.Path_Book import find_latest_QD_pkl_for_dr
from Modularize.support import init_meas, init_system_atte, shut_down
from Modularize.support.Pulse_schedule_library import mix_T1_sche, T1_sche, set_LO_frequency, pulse_preview, IQ_data_dis, dataset_to_array, T1_fit_analysis, Fit_analysis_plot

def T1(QD_agent:QDmanager,meas_ctrl:MeasurementControl,freeduration:float=80e-6,IF:int=150e6,n_avg:int=300,points:int=200,run:bool=True,q='q1',exp_idx:int=0, Experi_info:dict={},ref_IQ:list=[0,0],data_folder:str=''):

    T1_us = {}
    analysis_result = {}
  
    sche_func= T1_sche
    qubit_info = QD_agent.quantum_device.get_element(q)
    LO= qubit_info.clock_freqs.f01()+IF
    set_LO_frequency(QD_agent.quantum_device,q=q,module_type='drive',LO_frequency=LO)
    Para_free_Du = ManualParameter(name="free_Duration", unit="s", label="Time")
    Para_free_Du.batched = True
    gap = (freeduration*1e9 // points) + ((freeduration*1e9 // points)%4)
    samples = arange(4e-9,freeduration,gap*1e-9)
    
    sched_kwargs = dict(
        q=q,
        pi_amp={str(q):qubit_info.rxy.amp180()},
        pi_dura=qubit_info.rxy.duration(),
        freeduration=Para_free_Du,
        R_amp={str(q):qubit_info.measure.pulse_amp()},
        R_duration={str(q):qubit_info.measure.pulse_duration()},
        R_integration={str(q):qubit_info.measure.integration_time()},
        R_inte_delay=qubit_info.measure.acq_delay(),
        )
    exp_kwargs= dict(sweep_freeDu=['start '+'%E' %samples[0],'end '+'%E' %samples[-1]],
                     )
    if run:
        gettable = ScheduleGettable(
            QD_agent.quantum_device,
            schedule_function=sche_func,
            schedule_kwargs=sched_kwargs,
            real_imag=True,
            batched=True,
            )
        QD_agent.quantum_device.cfg_sched_repetitions(n_avg)
        meas_ctrl.gettables(gettable)
        meas_ctrl.settables(Para_free_Du)
        meas_ctrl.setpoints(samples)
        
        T1_ds = meas_ctrl.run('T1')
        # Save the raw data into netCDF
        Data_manager().save_raw_data(QD_agent=QD_agent,ds=T1_ds,label=exp_idx,qb=q,exp_type='T1',specific_dataFolder=data_folder)
        
        I,Q= dataset_to_array(dataset=T1_ds,dims=1)
        data= IQ_data_dis(I,Q,ref_I=ref_IQ[0],ref_Q=ref_IQ[-1])
        if data_folder == '':
            data_fit= T1_fit_analysis(data=data,freeDu=samples,T1_guess=14e-6)
            T1_us[q] = data_fit.attrs['T1_fit']*1e6
        else:
            data_fit=[]
            T1_us[q] = 0
        analysis_result[q] = data_fit
        
            
        show_args(exp_kwargs, title="T1_kwargs: Meas.qubit="+q)
  

        if Experi_info != {}:
            show_args(Experi_info(q))

        
    else:
        n_s = 2
        sweep_para= array(samples[:n_s])
        sched_kwargs['freeduration']= sweep_para.reshape(sweep_para.shape or (1,))
        pulse_preview(QD_agent.quantum_device,sche_func,sched_kwargs)
        

        show_args(exp_kwargs, title="T1_kwargs: Meas.qubit="+q)
        if Experi_info != {}:
            show_args(Experi_info(q))
    
        
  
    return analysis_result, T1_us


def T1_executor(QD_agent:QDmanager,cluster:Cluster,meas_ctrl:MeasurementControl,Fctrl:dict,specific_qubits:str,freeDura:float=30e-6,histo_counts:int=1,run:bool=True,specific_folder:str='',pts:int=100):
    if run:
        T1_us = []
        for ith in range(histo_counts):
            slightly_print(f"The {ith}-th T1:")
            Fctrl[specific_qubits](float(QD_agent.Fluxmanager.get_proper_zbiasFor(specific_qubits)))
            T1_results, T1_hist = T1(QD_agent,meas_ctrl,q=specific_qubits,freeduration=freeDura,ref_IQ=QD_agent.refIQ[specific_qubits],run=True,exp_idx=ith,data_folder=specific_folder,points=pts)
            Fctrl[specific_qubits](0.0)
            cluster.reset()
            T1_us.append(T1_hist[specific_qubits])
            
        T1_us = array(T1_us)
        mean_T1_us = round(mean(T1_us),1)
        sd_T1_us = round(std(T1_us),1)
        if histo_counts == 1:
            Fit_analysis_plot(T1_results[specific_qubits],P_rescale=False,Dis=None)
        else:
            if specific_folder == '': # when a folder given, the case should be only radiator test so far (2024/04/26) and i don't want it analyze 
                Data_manager().save_histo_pic(QD_agent,{str(specific_qubits):T1_us},specific_qubits,mode="t1",T1orT2=f"{mean_T1_us}+/-{sd_T1_us}",pic_folder=specific_folder)
        
    else:
        T1_results, T1_hist = T1(QD_agent,meas_ctrl,q=specific_qubits,exp_idx=0,freeduration=freeDura,ref_IQ=QD_agent.refIQ[specific_qubits],run=False)
        mean_T1_us = 0 
        sd_T1_us = 0
    
    return T1_results, mean_T1_us, sd_T1_us

if __name__ == "__main__":
    

    """ Fill in """
    execution = True
    DRandIP = {"dr":"dr1","last_ip":"11"}
    ro_elements = {
        "q0":{"evoT":100e-6,"histo_counts":1}
    }


    """ Preparations """
    QD_path = find_latest_QD_pkl_for_dr(which_dr=DRandIP["dr"],ip_label=DRandIP["last_ip"])
    QD_agent, cluster, meas_ctrl, ic, Fctrl = init_meas(QuantumDevice_path=QD_path,mode='l')
    
    
    
    """ Running """
    T1_results = {}
    for qubit in ro_elements:
        init_system_atte(QD_agent.quantum_device,list([qubit]),ro_out_att=QD_agent.Notewriter.get_DigiAtteFor(qubit,'ro'),xy_out_att=QD_agent.Notewriter.get_DigiAtteFor(qubit,'xy'))
        evoT = ro_elements[qubit]["evoT"]
        histo_total = ro_elements[qubit]["histo_counts"]

        T1_results[qubit], mean_T1_us, std_T1_us = T1_executor(QD_agent,cluster,meas_ctrl,Fctrl,qubit,freeDura=evoT,histo_counts=histo_total,run=execution)
        highlight_print(f"{qubit}: mean T1 = {mean_T1_us} 土 {std_T1_us} µs")
        
        
        """ Storing """
        if execution:
            if histo_total >= 50:
                QD_agent.Notewriter.save_T1_for(mean_T1_us,qubit)
                QD_agent.QD_keeper()


    """ Close """
    print('T1 done!')
    shut_down(cluster,Fctrl)