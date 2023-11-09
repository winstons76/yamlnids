# Code adapted from
# G. De Carvalho Bertoli et al., “An End-to-End Framework for Machine Learning-Based Network Intrusion Detection System,” IEEE Access, vol. 9, pp. 106790–106805, 2021, doi: 10.1109/ACCESS.2021.3101188.

import fnfqueue
from joblib import load
from pandas import DataFrame
from scapy.all import *
import sys

if len(sys.argv)<2:
    print("[Error] Incomplete line command.")
    print("------------------------------------")
    print("Usage: {0} model_name".format(sys.argv[0]))
    print("Available models: knn, dt")
else:
    accept_model = ['knn', 'dt']
    if sys.argv[1] in accept_model:
        model_name = sys.argv[1] + ".pkl"
        queue = 1

        conn = fnfqueue.Connection()
        preprocess = load(open("Models/preprocessor.pkl", "rb"))
        model = load(open("Models/"+model_name, "rb"))

        features = ['dst_port', 'ip_prot', 'flow_duration', 'down_up_ratio', 'pkt_len_max', 'bytes_per_s', 'pkt_per_s', 'fwd_pkt_cnt', 'fwd_pkt_len_tot', 'fwd_pkt_len_max']

        try:
            q = conn.bind(queue)
            q.set_mode(0xffff, fnfqueue.COPY_PACKET)
        except PermissionError:
            print("Access denied; Do I have root rights or the needed capabilities?")
            sys.exit(-1)

        while True:
            try:
                for packet in conn:
                    pkt = []
                    l3 = IP(packet.payload)
                    l4 = TCP(packet.payload)

                    pkt.append(l3.id)    #ip_id
                    pkt.append(l3.flags.DF & 1)  #ip_flag_df
                    pkt.append(l3.ttl)   #ip_ttl
                    pkt.append(l3.len)   #ip_len
                    pkt.append(l3.tos)     #ip_dsfield

                    pkt.append(l4.sport) #tcp_dport
                    pkt.append(l4.seq)   #tcp_seq
                    pkt.append(len(l4.payload))  #tcp_len
                    pkt.append(len(l4))  #tcp_hdr_len

                    # bitwise operation on the flags to retrieve the value
                    pkt.append(l4.flags.F & 1)   #tcp_flag_fin
                    pkt.append(l4.flags.S & 1)   #tcp_flag_syn
                    pkt.append(l4.flags.R & 1)   #tcp_flag_rst
                    pkt.append(l4.flags.P & 1)   #tcp_flag_push
                    pkt.append(l4.flags.A & 1)   #tcp_flag_ack
                    pkt.append(l4.flags.U & 1)   #tcp_flag_urg
                    pkt.append(l4.flags.C & 1)   #tcp_flag_cwr
                    pkt.append(l4.window)        #tcp_window_size
                    pkt.append(l4.urgptr)        #tcp_urgent_pointer
                    # to retrieve mss_val is required to look for this field in the TCP options
                    # normally this field is in the byte format, so the convertion to int from bytes is required
                    # if the field MSS is not set, the value is used as zero
                    pkt.append(next((int.from_bytes(x[1], byteorder=sys.byteorder) for x in l4.options if x[0] == "MSS"), 0)) #tcp_options_mss_val

                    df = DataFrame([pkt], columns=features)

                    X = preprocess.transform(df)
                    # the pre-processing transform pandas dataframe to numpy array
                    # to make XGBoost work it is required to get back to dataframe format
                    X = DataFrame(X, columns=features)
                    predict = model.predict(X)

                    if predict == 0:    #the model predict the packet as bonafide
                        packet.accept()
                    else:               #the model precict the packet as attack
                        packet.drop()

            except fnfqueue.BufferOverflowException:
                print("buffer error")

        conn.close()
    else:
        print("[Error] Wrong model name.")

