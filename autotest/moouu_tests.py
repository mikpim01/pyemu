import os
import sys

#sys.path.append(os.path.join("..","pyemu"))
import pyemu
from pyemu.prototypes.moouu import EvolAlg, EliteDiffEvol, ParetoObjFunc
#path = os.path.join(os.getcwd(), 'autotest', 'moouu', '10par_xsec', '10par_xsec.pst')


if not os.path.exists("temp1"):
    os.mkdir("temp1")

def test_paretoObjFunc():
    import pyemu
    import os
    os.chdir(os.path.join('moouu', 'StochasticProblemSuite'))
    pst = pyemu.Pst('SRN.pst')
    obj_dict = {pst.obs_names[0]: 'min', pst.obs_names[1]: 'min'}
    dv_names = pst.par_names
    d_vars = pyemu.ParameterEnsemble.from_mixed_draws(pst=pst, how_dict={dv: 'uniform'for dv in dv_names},
                                                      partial=True, num_reals=5)
    ga = EliteDiffEvol(pst=pst, num_slaves=4, verbose=True)
    ga.initialize(obj_func_dict=obj_dict, num_par_reals=5, num_dv_reals=5, dv_ensemble=d_vars)


def tenpar_test():
    import os
    import numpy as np
    import flopy
    import pyemu

    bd = os.getcwd()
    try:
        #os.chdir(os.path.join("moouu","10par_xsec"))
        os.chdir(os.path.join("moouu", 'StochasticProblemSuite'))
        csv_files = [f for f in os.listdir('.') if f.endswith(".csv")]
        [os.remove(csv_file) for csv_file in csv_files]
        #pst = pyemu.Pst("10par_xsec.pst")
        pst = pyemu.Pst('SRN.pst')
        obj_names = pst.nnz_obs_names
        # pst.observation_data.loc[pst.obs_names[0],"obgnme"] = "greaterthan"
        # pst.observation_data.loc[pst.obs_names[0], "weight"] = 1.0
        # pst.observation_data.loc[pst.obs_names[0], "obsval"] *= 0.85
        # pst.observation_data.loc[pst.obs_names[-1], "obgnme"] = "greaterthan"
        # pst.observation_data.loc[pst.obs_names[-1], "weight"] = 1.0
        # pst.observation_data.loc[pst.obs_names[-1], "obsval"] *= 0.85

        # pst.observation_data.loc["h01_10", "obgnme"] = "greaterthan"
        # pst.observation_data.loc["h01_10", "weight"] = 1.0
        #pst.observation_data.loc["h01_10", "obsval"] *= 0.85


        par = pst.parameter_data
        #par.loc[:,"partrans"] = "none"

        obj_dict = {}
        obj_dict[obj_names[0]] = "min"
        obj_dict[obj_names[1]] = "min"



        # testing for reduce method
        # oe = pyemu.ObservationEnsemble.from_id_gaussian_draw(pst=pst, num_reals=5000)
        # logger = pyemu.Logger("temp.log")
        # obj_func = evol_proto.ParetoObjFunc(pst,obj_dict,logger)
        # df = obj_func.reduce_stack_with_risk_shift(oe,50,0.05)
        #
        # import matplotlib.pyplot as plt
        # ax = plt.subplot(111)
        # oe.iloc[:, -1].hist(ax=ax)
        # ylim = ax.get_ylim()
        # val = df.iloc[0,-1]
        # ax.plot([val, val], ylim)
        # ax.set_ylim(ylim)
        # plt.show()
        # print(df.shape)
        # return
        pe = pyemu.ParameterEnsemble.from_mixed_draws(pst=pst, how_dict={p: "gaussian" for p in pst.adj_par_names[2:]},
                                                      num_reals=5,
                                                      partial=False)
        ea = EliteDiffEvol(pst, num_slaves=8, port=4005, verbose=True)

        dv = pyemu.ParameterEnsemble.from_mixed_draws(pst=pst, how_dict={p: "uniform" for p in pst.adj_par_names[:2]},
                                                      num_reals=5,
                                                      partial=True)

        ea.initialize(obj_dict,num_dv_reals=5,num_par_reals=5,risk=0.5)
        ea.initialize(obj_dict, par_ensemble=pe, dv_ensemble=dv, risk=0.5)

        #ea.update()


        # test the infeas calcs
    #     oe = ea.obs_ensemble
    #     ea.obj_func.is_nondominated_continuous(oe)
    #     ea.obj_func.is_nondominated_kung(oe)
    #     is_feasible = ea.obj_func.is_feasible(oe)
    #     oe.loc[is_feasible.index,"feas"] = is_feasible
    #     obs = pst.observation_data
    #     for lt_obs in pst.less_than_obs_constraints:
    #         val = obs.loc[lt_obs,"obsval"]
    #         infeas = oe.loc[:,lt_obs] >= val
    #         assert np.all(~is_feasible.loc[infeas])
    #
    #     for gt_obs in pst.greater_than_obs_constraints:
    #         val = obs.loc[gt_obs,"obsval"]
    #         infeas = oe.loc[:,gt_obs] <= val
    #         assert np.all(~is_feasible.loc[infeas])
    #
    #     # test that the end members are getting max distance
    #     crowd_distance = ea.obj_func.crowd_distance(oe)
    #     for name,direction in ea.obj_func.obs_dict.items():
    #         assert crowd_distance.loc[oe.loc[:,name].idxmax()] >= ea.obj_func.max_distance,crowd_distance.loc[oe.loc[:,name].idxmax()]
    #         assert crowd_distance.loc[oe.loc[:, name].idxmin()] >= ea.obj_func.max_distance,crowd_distance.loc[oe.loc[:, name].idxmin()]
    except Exception as e:
        os.chdir(os.path.join("..",".."))
        raise Exception(str(e))

    os.chdir(os.path.join("..",".."))


def tenpar_dev():
    import os
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    import flopy
    import pyemu

    os.chdir(os.path.join("moouu","10par_xsec"))
    csv_files = [f for f in os.listdir('.') if f.endswith(".csv")]
    [os.remove(csv_file) for csv_file in csv_files]
    pst = pyemu.Pst("10par_xsec.pst")
    #obj_names = pst.nnz_obs_names
    obj_names = ["h01_04", "h01_06"]

    # pst.observation_data.loc[pst.obs_names[0],"obgnme"] = "greaterthan"
    # pst.observation_data.loc[pst.obs_names[0], "weight"] = 1.0
    # pst.observation_data.loc[pst.obs_names[0], "obsval"] *= 0.85
    # pst.observation_data.loc[pst.obs_names[-1], "obgnme"] = "greaterthan"
    # pst.observation_data.loc[pst.obs_names[-1], "weight"] = 1.0
    # pst.observation_data.loc[pst.obs_names[-1], "obsval"] *= 0.85

    # pst.observation_data.loc["h01_10", "obgnme"] = "lessthan"
    # pst.observation_data.loc["h01_10", "weight"] = 1.0
    # pst.observation_data.loc["h01_10", "obsval"] *= 0.85


    par = pst.parameter_data
    par.loc[:,"partrans"] = "none"


    obj_dict = {}
    obj_dict[obj_names[0]] = "min"
    obj_dict[obj_names[1]] = "max"
    #obj_dict[obj_names[2]] = "max"

    # testing for reduce method
    # oe = pyemu.ObservationEnsemble.from_id_gaussian_draw(pst=pst, num_reals=5000)
    # logger = pyemu.Logger("temp.log")
    # obj_func = evol_proto.ParetoObjFunc(pst,obj_dict,logger)
    # df = obj_func.reduce_stack_with_risk_shift(oe,50,0.05)
    #
    # import matplotlib.pyplot as plt
    # ax = plt.subplot(111)
    # oe.iloc[:, -1].hist(ax=ax)
    # ylim = ax.get_ylim()
    # val = df.iloc[0,-1]
    # ax.plot([val, val], ylim)
    # ax.set_ylim(ylim)
    # plt.show()
    # print(df.shape)
    # return
    dv_names = pst.adj_par_names[2:]
    par_names = pst.adj_par_names[:2]
    par.loc[dv_names, "parlbnd"] = 1.0
    par.loc[dv_names, "parubnd"] = 5.0

    pe = pyemu.ParameterEnsemble.from_mixed_draws(pst=pst, how_dict={p: "uniform" for p in par_names},
                                                 num_reals=1,
                                                 partial=False)


    dv = pyemu.ParameterEnsemble.from_mixed_draws(pst=pst, how_dict={p: "uniform" for p in dv_names},
                                                  num_reals=10,
                                                  partial=True)

    dv.index = ["p_{0}".format(i) for i in range(dv.shape[0])]
    ea = EliteDiffEvol(pst, num_slaves=5, port=4005, verbose=True)

    ea.initialize(obj_dict,par_ensemble=pe,dv_ensemble=dv,risk=0.5)



    #ax = plt.subplot(111)
    obj_org = ea.obs_ensemble.loc[:, obj_names].copy()
    dom_org = ea.obj_func.is_nondominated(obj_org)


    axes = pd.plotting.scatter_matrix(obj_org)
    print(axes)
    axes[0,0].set_xlim(0,4)
    axes[1, 1].set_xlim(0, 4)
    axes[0,1].set_xlim(0,4)
    axes[0,1].set_ylim(0,4)
    axes[1, 0].set_xlim(0, 4)
    axes[1, 0].set_ylim(0, 4)

    #plt.show()
    plt.savefig("iter_{0:03d}.png".format(0))
    plt.close("all")
    for i in range(30):

        ea.update()

        obj = ea.obs_ensemble.loc[:, obj_names]
        axes = pd.plotting.scatter_matrix(obj)
        print(axes)
        axes[0, 0].set_xlim(0, 4)
        axes[1, 1].set_xlim(0, 4)
        axes[0, 1].set_xlim(0, 4)
        axes[0, 1].set_ylim(0, 4)
        axes[1, 0].set_xlim(0, 4)
        axes[1, 0].set_ylim(0, 4)

        plt.savefig("iter_{0:03d}.png".format(i+1))
        plt.close("all")

    os.system("ffmpeg -r 2 -i iter_%03d.png -loop 0 -final_delay 100 -y shhh.mp4")
    return
    ax = plt.subplot(111)
    colors = ['r','y','g','b','m']
    risks = [0.05,0.25,0.51,0.75,0.95]
    for risk,color in zip(risks,colors):
        ea.initialize(obj_dict,par_ensemble=pe,dv_ensemble=dv,risk=risk,dv_names=pst.adj_par_names[2:])
        oe = ea.obs_ensemble
        # call the nondominated sorting
        is_nondom = ea.obj_func.is_nondominated(oe)
        obj = oe.loc[:,obj_names]
        obj.loc[is_nondom,"is_nondom"] = is_nondom
        #print(obj)

        stack = ea.last_stack
        plt.scatter(stack.loc[:, obj_names[0]], stack.loc[:, obj_names[1]], color="0.5", marker='.',s=10, alpha=0.25)

        plt.scatter(obj.loc[:,obj_names[0]],obj.loc[:,obj_names[1]],color=color,marker='.',alpha=0.25,s=8)
        ind = obj.loc[is_nondom,:]
        #plt.scatter(ind.iloc[:, 0], ind.iloc[:, 1], color="m", marker='.',s=8,alpha=0.5)
        isfeas = ea.obj_func.is_feasible(oe)

        isf = obj.loc[isfeas,:]
        #plt.scatter(isf.iloc[:, 0], isf.iloc[:, 1], color="g", marker='.', s=30, alpha=0.5)
        both = [True if s and d else False for s,d in zip(is_nondom,isfeas)]
        both = obj.loc[both,:]
        plt.scatter(both.loc[:, obj_names[0]], both.loc[:, obj_names[1]], color=color, marker='+', s=90,alpha=0.5)

    ax.set_xlabel("{0}, dir:{1}".format(obj_names[0],obj_dict[obj_names[0]]))
    ax.set_ylabel("{0}, dir:{1}".format(obj_names[1], obj_dict[obj_names[1]]))
    plt.savefig("risk_compare.pdf")
    #plt.show()

    os.chdir(os.path.join("..",".."))


def setup_freyberg_transport():
    import os
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import flopy
    import pyemu


    org_model_ws = os.path.join("..","examples","freyberg_sfr_reaches")
    new_model_ws = os.path.join("moouu","freyberg","temp")
    mf_nam = "freyberg.nam"
    mt_nam = "freyberg_mt.nam"

    mf = flopy.modflow.Modflow.load(mf_nam,model_ws=org_model_ws,verbose=True,version="mfnwt",exe_name="mfnwt")
    mf.dis.nper = 1
    mf.dis.perlen = 3650.0
    mf.external_path = '.'
    mf.change_model_ws(new_model_ws,reset_external=True)

    mf.write_input()
    mf.run_model()

    # hds = flopy.utils.HeadFile(os.path.join(new_model_ws,mf_nam.replace(".nam",".hds")),model=mf)
    # hds.plot()
    # plt.show()

    mt = flopy.mt3d.Mt3dms.load(mt_nam,model_ws=org_model_ws,verbose=True,exe_name="mt3dusgs",modflowmodel=mf)

    mt.btn.nper = 1
    mt.btn.perlen = 3650.0
    #mt.external_path = '.'
    mt.remove_package("SSM")
    spd = []
    ib = mf.bas6.ibound[0].array
    for i in range(mf.nrow):
        for j in range(mf.ncol):
            if ib[i,j] <= 0:
                continue
            spd.append([0,i,j,1.0,15])

    flopy.mt3d.Mt3dSsm(mt,crch=0.0,stress_period_data=spd,mxss=10000)
    mt.change_model_ws(new_model_ws,reset_external=True)
    mt.sft.nsfinit = 40
    mt.sft.nobssf = 40
    mt.sft.obs_sf = np.arange(mt.sft.nsfinit) + 1
    mt.write_input()
    mt.run_model()

    # unc = flopy.utils.UcnFile(os.path.join(new_model_ws,"MT3D001.UCN"),model=mf)
    # unc.plot(colorbar=True,masked_values=[1.0e30])
    # plt.show()
    return new_model_ws


def setup_freyberg_pest_interface():
    import os
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import flopy
    import pyemu

    org_model_ws = setup_freyberg_transport()

    props = []
    paks = ["upw.hk","upw.vka","extra.prst","extra.rc11","extra.scn1"]
    for k in range(3):
        for p in paks:
            props.append([p,k])
    props.append(["rch.rech",0])


    ph = pyemu.helpers.PstFromFlopyModel("freyberg.nam",org_model_ws=org_model_ws,new_model_ws="template",remove_existing=True,
                                         grid_props=props,spatial_bc_props=["wel.flux",2],hds_kperk=[[0,0],[0,1],[0,2]],
                                         mflist_waterbudget=True,sfr_pars=True,build_prior=False,extra_post_cmds=["mt3dusgs freyberg_mt.nam >mt_stdout"])

    pyemu.helpers.run("mfnwt freyberg.nam", cwd=ph.m.model_ws)
    mt = flopy.mt3d.Mt3dms.load("freyberg_mt.nam", model_ws=org_model_ws, verbose=True, exe_name="mt3dusgs")
    mt.external_path = '.'
    mt.change_model_ws("template",reset_external=True)
    mt.write_input()
    pyemu.helpers.run("mt3dusgs freyberg_mt.nam",cwd="template")

    tpl_file = write_ssm_tpl(os.path.join("template","freyberg_mt.ssm"))


def write_ssm_tpl(ssm_file):

    f_in = open(ssm_file,'r')
    tpl_file = ssm_file + ".tpl"
    f_tpl = open(tpl_file,'w')
    f_tpl.write("ptf ~\n")
    while True:
        line = f_in.readline()
        if line == '':
            break
        f_tpl.write(line)
        if "stress period" in line.lower():
            #f_tpl.write(line)
            while True:
                line = f_in.readline()
                if line == '':
                    break
                raw = line.strip().split()
                i = int(raw[1]) - 1
                j = int(raw[2]) - 1
                pname = "k{0:02d}_{1:02d}".format(i,j)
                tpl_str = "~{0}~ ".format(pname)
                line = line[:39] + tpl_str + line[48:]
                #print(line)
                f_tpl.write(line)


if __name__ == "__main__":
    test_paretoObjFunc()
    #tenpar_test()
    #quick_tests()
    #tenpar_test()
    #tenpar_dev()
    #setup_freyberg_transport()
    #setup_freyberg_pest_interface()
