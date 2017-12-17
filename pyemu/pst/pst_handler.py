"""This module contains most of the pyemu.Pst object definition.  This object
is the primary mechanism for dealing with PEST control files
"""

from __future__ import print_function, division
import os
import re
import copy
import warnings
import numpy as np
import pandas as pd
pd.options.display.max_colwidth = 100
from pyemu.pst.pst_controldata import ControlData, SvdData, RegData
from pyemu.pst import pst_utils

class Pst(object):
    """basic class for handling pest control files to support linear analysis
    as well as replicate some of the functionality of the pest utilities

    Parameters
    ----------
    filename : str
        the name of the control file
    load : (boolean)
        flag to load the control file. Default is True
    resfile : str
        corresponding residual file.  If None, a residual file
        with the control file base name is sought.  Default is None

    Returns
    -------
    Pst : Pst
        a control file object

    """
    def __init__(self, filename, load=True, resfile=None):


        self.filename = filename
        self.resfile = resfile
        self.__res = None
        self.__pi_count = 0
        for key,value in pst_utils.pst_config.items():
            self.__setattr__(key,copy.copy(value))
        self.tied = None
        self.control_data = ControlData()
        self.svd_data = SvdData()
        self.reg_data = RegData()
        if load:
            assert os.path.exists(filename),\
                "pst file not found:{0}".format(filename)
            self.load(filename)

    def __setattr__(self, key, value):
        if key == "model_command":
            if isinstance(value, str):
                value = [value]
        super(Pst,self).__setattr__(key,value)

    @property
    def phi(self):
        """get the weighted total objective function

        Returns
        -------
        phi : float
            sum of squared residuals

        """
        sum = 0.0
        for grp, contrib in self.phi_components.items():
            sum += contrib
        return sum

    @property
    def phi_components(self):
        """ get the individual components of the total objective function

        Returns
        -------
        dict : dict
            dictionary of observation group, contribution to total phi

        Raises
        ------
        Assertion error if Pst.observation_data groups don't match
        Pst.res groups

        """

        # calculate phi components for each obs group
        components = {}
        ogroups = self.observation_data.groupby("obgnme").groups
        rgroups = self.res.groupby("group").groups
        for og in ogroups.keys():
            assert og in rgroups.keys(),"Pst.adjust_weights_res() obs group " +\
                "not found: " + str(og)
            og_res_df = self.res.ix[rgroups[og]]
            og_res_df.index = og_res_df.name
            og_df = self.observation_data.ix[ogroups[og]]
            og_df.index = og_df.obsnme
            og_res_df = og_res_df.loc[og_df.index,:]
            assert og_df.shape[0] == og_res_df.shape[0],\
            " Pst.phi_components error: group residual dataframe row length" +\
            "doesn't match observation data group dataframe row length" + \
                str(og_df.shape) + " vs. " + str(og_res_df.shape)
            components[og] = np.sum((og_res_df["residual"] *
                                     og_df["weight"]) ** 2)
        if not self.control_data.pestmode.startswith("reg") and \
            self.prior_information.shape[0] > 0:
            ogroups = self.prior_information.groupby("obgnme").groups
            for og in ogroups.keys():
                assert og in rgroups.keys(),"Pst.adjust_weights_res() obs group " +\
                    "not found: " + str(og)
                og_res_df = self.res.ix[rgroups[og]]
                og_res_df.index = og_res_df.name
                og_df = self.prior_information.ix[ogroups[og]]
                og_df.index = og_df.pilbl
                og_res_df = og_res_df.loc[og_df.index,:]
                assert og_df.shape[0] == og_res_df.shape[0],\
                " Pst.phi_components error: group residual dataframe row length" +\
                "doesn't match observation data group dataframe row length" + \
                    str(og_df.shape) + " vs. " + str(og_res_df.shape)
                components[og] = np.sum((og_res_df["residual"] *
                                         og_df["weight"]) ** 2)

        return components

    @property
    def phi_components_normalized(self):
        """ get the individual components of the total objective function
            normalized to the total PHI being 1.0

        Returns
        -------
        dict : dict
            dictionary of observation group, normalized contribution to total phi

        Raises
        ------
        Assertion error if self.observation_data groups don't match
        self.res groups

        """
        # use a dictionary comprehension to go through and normalize each component of phi to the total
        phi_components_normalized = {i: self.phi_components[i]/self.phi for i in self.phi_components}
        return phi_components_normalized

    def set_res(self,res):
        """ reset the private Pst.res attribute

        Parameters
        ----------
        res : (varies)
            something to use as Pst.res attribute

        """
        self.__res = res

    @property
    def res(self):
        """get the residuals dataframe attribute

        Returns
        -------
        res : pandas.DataFrame

        Note
        ----
        if the Pst.__res attribute has not been loaded,
        this call loads the res dataframe from a file

        """
        if self.__res is not None:
            return self.__res
        else:
            if self.resfile is not None:
                assert os.path.exists(self.resfile),"Pst.res: self.resfile " +\
                    str(self.resfile) + " does not exist"
            else:
                self.resfile = self.filename.replace(".pst", ".res")
                if not os.path.exists(self.resfile):
                    self.resfile = self.resfile.replace(".res", ".rei")
                    if not os.path.exists(self.resfile):
                        raise Exception("Pst.res: " +
                                        "could not residual file case.res" +
                                        " or case.rei")

            res = pst_utils.read_resfile(self.resfile)
            missing_bool = self.observation_data.obsnme.apply\
                (lambda x: x not in res.name)
            missing = self.observation_data.obsnme[missing_bool]
            if missing.shape[0] > 0:
                raise Exception("Pst.res: the following observations " +
                                "were not found in " +
                                "{0}:{1}".format(self.resfile,','.join(missing)))
            self.__res = res
            return self.__res

    @property
    def nprior(self):
        """number of prior information equations

        Returns
        -------
        nprior : int
            the number of prior info equations

        """
        self.control_data.nprior = self.prior_information.shape[0]
        return self.control_data.nprior

    @property
    def nnz_obs(self):
        """ get the number of non-zero weighted observations

        Returns
        -------
        nnz_obs : int
            the number of non-zeros weighted observations

        """
        nnz = 0
        for w in self.observation_data.weight:
            if w > 0.0:
                nnz += 1
        return nnz


    @property
    def nobs(self):
        """get the number of observations

        Returns
        -------
        nobs : int
            the number of observations

        """
        self.control_data.nobs = self.observation_data.shape[0]
        return self.control_data.nobs


    @property
    def npar_adj(self):
        """get the number of adjustable parameters (not fixed or tied)

        Returns
        -------
        npar_adj : int
            the number of adjustable parameters

        """
        pass
        np = 0
        for t in self.parameter_data.partrans:
            if t not in ["fixed", "tied"]:
                np += 1
        return np


    @property
    def npar(self):
        """get number of parameters

        Returns
        -------
        npar : int
            the number of parameters

        """
        self.control_data.npar = self.parameter_data.shape[0]
        return self.control_data.npar


    @property
    def forecast_names(self):
        """get the forecast names from the pestpp options (if any).
        Returns None if no forecasts are named

        Returns
        -------
        forecast_names : list
            a list of forecast names.

        """
        if "forecasts" in self.pestpp_options.keys():
            return self.pestpp_options["forecasts"].lower().split(',')
        elif "predictions" in self.pestpp_options.keys():
            return self.pestpp_options["predictions"].lower().split(',')
        else:
            return None

    @property
    def obs_groups(self):
        """get the observation groups

        Returns
        -------
        obs_groups : list
            a list of unique observation groups

        """
        og = list(self.observation_data.groupby("obgnme").groups.keys())
        #og = list(map(pst_utils.SFMT, og))
        return og

    @property
    def nnz_obs_groups(self):
        """ get the observation groups that contain at least one non-zero weighted
         observation

        Returns
        -------
        nnz_obs_groups : list
            a list of observation groups that contain at
            least one non-zero weighted observation

        """
        og = []
        obs = self.observation_data
        for g in self.obs_groups:
            if obs.loc[obs.obgnme==g,"weight"].sum() > 0.0:
                og.append(g)
        return og


    @property
    def par_groups(self):
        """get the parameter groups

        Returns
        -------
        par_groups : list
            a list of parameter groups

        """
        pass
        return list(self.parameter_data.groupby("pargp").groups.keys())


    @property
    def prior_groups(self):
        """get the prior info groups

        Returns
        -------
        prior_groups : list
            a list of prior information groups

        """
        og = list(self.prior_information.groupby("obgnme").groups.keys())
        #og = list(map(pst_utils.SFMT, og))
        return og

    @property
    def prior_names(self):
        """ get the prior information names

        Returns
        -------
        prior_names : list
            a list of prior information names

        """
        return list(self.prior_information.groupby(
                self.prior_information.index).groups.keys())

    @property
    def par_names(self):
        """get the parameter names

        Returns
        -------
        par_names : list
            a list of parameter names
        """
        return list(self.parameter_data.parnme.values)

    @property
    def adj_par_names(self):
        """ get the adjustable (not fixed or tied) parameter names

        Returns
        -------
        adj_par_names : list
            list of adjustable (not fixed or tied) parameter names

        """
        adj_names = []
        for t,n in zip(self.parameter_data.partrans,
                       self.parameter_data.parnme):
            if t.lower() not in ["tied","fixed"]:
                adj_names.append(n)
        return adj_names

    @property
    def obs_names(self):
        """get the observation names

        Returns
        -------
        obs_names : list
            a list of observation names

        """
        pass
        return list(self.observation_data.obsnme.values)

    @property
    def nnz_obs_names(self):
        """get the non-zero weight observation names

        Returns
        -------
        nnz_obs_names : list
            a list of non-zero weighted observation names

        """
        nz_names = []
        for w,n in zip(self.observation_data.weight,
                       self.observation_data.obsnme):
            if w > 0.0:
                nz_names.append(n)
        return nz_names

    @property
    def zero_weight_obs_names(self):
        """ get the zero-weighted observation names

        Returns
        -------
         zero_weight_obs_names : list
             a list of zero-weighted observation names

        """
        self.observation_data.index = self.observation_data.obsnme
        groups = self.observation_data.groupby(
                self.observation_data.weight.apply(lambda x: x==0.0)).groups
        if True in groups:
            return list(self.observation_data.loc[groups[True],"obsnme"])
        else:
            return []

    # @property
    # def regul_section(self):
    #     phimlim = float(self.nnz_obs)
    #     #sect = "* regularisation\n"
    #     sect = "{0:15.6E} {1:15.6E}\n".format(phimlim, phimlim*1.15)
    #     sect += "1.0 1.0e-10 1.0e10 linreg continue\n"
    #     sect += "1.3  1.0e-2  1\n"
    #     return sect

    @property
    def estimation(self):
        """ check if the control_data.pestmode is set to estimation

        Returns
        -------
        estimation : bool
            True if pestmode is estmation, False otherwise

        """
        if self.control_data.pestmode == "estimation":
            return True
        return False

    @staticmethod
    def _read_df(f,nrows,names,converters,defaults=None):
        """ a private method to read part of an open file into a pandas.DataFrame.

        Parameters
        ----------
        f : file object
        nrows : int
            number of rows to read
        names : list
            names to set the columns of the dataframe with
        converters : dict
            dictionary of lambda functions to convert strings
            to numerical format
        defaults : dict
            dictionary of default values to assign columns.
            Default is None

        Returns
        -------
        pandas.DataFrame : pandas.DataFrame

        """
        seek_point = f.tell()
        df = pd.read_csv(f, header=None,names=names,
                              nrows=nrows,delim_whitespace=True,
                              converters=converters, index_col=False)

        # in case there was some extra junk at the end of the lines
        if df.shape[1] > len(names):
            df = df.iloc[:,len(names)]
            df.columns = names

        if defaults is not None:
            for name in names:
                df.loc[:,name] = df.loc[:,name].fillna(defaults[name])
        elif np.any(pd.isnull(df)):
            raise Exception("NANs found")
        f.seek(seek_point)
        [f.readline() for _ in range(nrows)]
        return df

    def load(self, filename):
        """load the pest control file information

        Parameters
        ----------
        filename : str
            pst filename

        Raises
        ------
            lots of exceptions for incorrect format

        """

        f = open(filename, 'r')
        f.readline()

        #control section
        line = f.readline()
        assert "* control data" in line,\
            "Pst.load() error: looking for control" +\
            " data section, found:" + line
        control_lines = []
        while True:
            line = f.readline()
            if line == '':
                raise Exception("Pst.load() EOF while " +\
                                "reading control data section")
            if line.startswith('*'):
                break
            control_lines.append(line)
        self.control_data.parse_values_from_lines(control_lines)


        #anything between control data and SVD
        while True:
            if line == '':
                raise Exception("EOF before parameter groups section found")
            if "* singular value decomposition" in line.lower() or\
                "* parameter groups" in line.lower():
                break
            self.other_lines.append(line)
            line = f.readline()

        if "* singular value decomposition" in line.lower():
            svd_lines = []
            for _ in range(3):
                line = f.readline()
                if line == '':
                    raise Exception("EOF while reading SVD section")
                svd_lines.append(line)
            self.svd_data.parse_values_from_lines(svd_lines)
            line = f.readline()
        while True:
            if line == '':
                raise Exception("EOF before parameter groups section found")
            if "* parameter groups" in line.lower():
                break
            self.other_lines.append(line)
            line = f.readline()

        #parameter data
        assert "* parameter groups" in line.lower(),\
            "Pst.load() error: looking for parameter" +\
            " group section, found:" + line
        try:
            self.parameter_groups = self._read_df(f,self.control_data.npargp,
                                                  self.pargp_fieldnames,
                                                  self.pargp_converters,
                                                  self.pargp_defaults)
            self.parameter_groups.index = self.parameter_groups.pargpnme
        except Exception as e:
            raise Exception("Pst.load() error reading parameter groups: {0}".format(str(e)))

        #parameter data
        line = f.readline()
        assert "* parameter data" in line.lower(),\
            "Pst.load() error: looking for parameter" +\
            " data section, found:" + line
        try:
            self.parameter_data = self._read_df(f,self.control_data.npar,
                                                self.par_fieldnames,
                                                self.par_converters,
                                                self.par_defaults)
            self.parameter_data.index = self.parameter_data.parnme
        except:
            raise Exception("Pst.load() error reading parameter data")

        # oh the tied parameter bullshit, how do I hate thee
        counts = self.parameter_data.partrans.value_counts()
        if "tied" in counts.index:
            # tied_lines = [f.readline().lower().strip().split() for _ in range(counts["tied"])]
            # self.tied = pd.DataFrame(tied_lines,columns=["parnme","partied"])
            # self.tied.index = self.tied.pop("parnme")
            self.tied = self._read_df(f,counts["tied"],self.tied_fieldnames,
                                      self.tied_converters)
            self.tied.index = self.tied.parnme
        # obs groups - just read past for now
        line = f.readline()
        assert "* observation groups" in line.lower(),\
            "Pst.load() error: looking for obs" +\
            " group section, found:" + line
        [f.readline() for _ in range(self.control_data.nobsgp)]

        # observation data
        line = f.readline()
        assert "* observation data" in line.lower(),\
            "Pst.load() error: looking for observation" +\
            " data section, found:" + line
        if self.control_data.nobs > 0:
            try:
                self.observation_data = self._read_df(f,self.control_data.nobs,
                                                      self.obs_fieldnames,
                                                      self.obs_converters)
                self.observation_data.index = self.observation_data.obsnme
            except:
                raise Exception("Pst.load() error reading observation data")
        else:
            raise Exception("nobs == 0")
        #model command line
        line = f.readline()
        assert "* model command line" in line.lower(),\
            "Pst.load() error: looking for model " +\
            "command section, found:" + line
        for i in range(self.control_data.numcom):
            self.model_command.append(f.readline().strip())

        #model io
        line = f.readline()
        assert "* model input/output" in line.lower(), \
            "Pst.load() error; looking for model " +\
            " i/o section, found:" + line
        for i in range(self.control_data.ntplfle):
            raw = f.readline().strip().split()
            self.template_files.append(raw[0])
            self.input_files.append(raw[1])
        for i in range(self.control_data.ninsfle):
            raw = f.readline().strip().split()
            self.instruction_files.append(raw[0])
            self.output_files.append(raw[1])

        #prior information - sort of hackish
        if self.control_data.nprior == 0:
            self.prior_information = self.null_prior
        else:
            pilbl, obgnme, weight, equation = [], [], [], []
            line = f.readline()
            assert "* prior information" in line.lower(), \
                "Pst.load() error; looking for prior " +\
                " info section, found:" + line
            for iprior in range(self.control_data.nprior):
                line = f.readline()
                if line == '':
                    raise Exception("EOF during prior information " +
                                    "section")
                raw = line.strip().split()
                pilbl.append(raw[0].lower())
                obgnme.append(raw[-1].lower())
                weight.append(float(raw[-2]))
                eq = ' '.join(raw[1:-2])
                equation.append(eq)
            self.prior_information = pd.DataFrame({"pilbl": pilbl,
                                                       "equation": equation,
                                                       "weight": weight,
                                                       "obgnme": obgnme})
            self.prior_information.index = self.prior_information.pilbl
        if "regul" in self.control_data.pestmode:
            line = f.readline()
            assert "* regul" in line.lower(), \
                "Pst.load() error; looking for regul " +\
                " section, found:" + line
            #[self.regul_lines.append(f.readline()) for _ in range(3)]
            regul_lines = [f.readline() for _ in range(3)]
            raw = regul_lines[0].strip().split()
            self.reg_data.phimlim = float(raw[0])
            self.reg_data.phimaccept = float(raw[1])
            raw = regul_lines[1].strip().split()
            self.wfinit = float(raw[0])


        for line in f:
            if line.strip().startswith("++") and '#' not in line:
                args = line.replace('++','').strip().split()
                #args = ['++'+arg.strip() for arg in args]
                #self.pestpp_lines.extend(args)
                keys = [arg.split('(')[0] for arg in args]
                values = [arg.split('(')[1].replace(')','') for arg in args]
                for key,value in zip(keys,values):
                    if key in self.pestpp_options:
                        print("Pst.load() warning: duplicate pest++ option found:" + str(key))
                    self.pestpp_options[key] = value
        f.close()

        return


    def _update_control_section(self):
        """ private method to synchronize the control section counters with the
        various parts of the control file.  This is usually called during the
        Pst.write() method.

        """
        self.control_data.npar = self.npar
        self.control_data.nobs = self.nobs
        self.control_data.npargp = self.parameter_groups.shape[0]
        self.control_data.nobsgp = self.observation_data.obgnme.\
            value_counts().shape[0] + self.prior_information.obgnme.\
            value_counts().shape[0]

        self.control_data.nprior = self.prior_information.shape[0]
        self.control_data.ntplfle = len(self.template_files)
        self.control_data.ninsfle = len(self.instruction_files)
        self.control_data.numcom = len(self.model_command)

    def _rectify_pgroups(self):
        """ private method to synchronize parameter groups section with
        the parameter data section


        """
        # add any parameters groups
        pdata_groups = list(self.parameter_data.loc[:,"pargp"].\
            value_counts().keys())
        #print(pdata_groups)
        need_groups = []
        existing_groups = list(self.parameter_groups.pargpnme)
        for pg in pdata_groups:
            if pg not in existing_groups:
                need_groups.append(pg)
        if len(need_groups) > 0:
            #print(need_groups)
            defaults = copy.copy(pst_utils.pst_config["pargp_defaults"])
            for grp in need_groups:
                defaults["pargpnme"] = grp
                self.parameter_groups = \
                    self.parameter_groups.append(defaults,ignore_index=True)

        # now drop any left over groups that aren't needed
        for gp in self.parameter_groups.loc[:,"pargpnme"]:
            if gp in pdata_groups and gp not in need_groups:
                need_groups.append(gp)
        self.parameter_groups.index = self.parameter_groups.pargpnme
        self.parameter_groups = self.parameter_groups.loc[need_groups,:]


    def _parse_pi_par_names(self):
        """ private method to get the parameter names from prior information
        equations.  Sets a 'names' column in Pst.prior_information that is a list
        of parameter names


        """
        if self.prior_information.shape[0] == 0:
            return
        if "names" in self.prior_information.columns:
            self.prior_information.pop("names")
        if "rhs" in self.prior_information.columns:
            self.prior_information.pop("rhs")
        def parse(eqs):
            raw = eqs.split('=')
            rhs = float(raw[1])
            raw = re.split('[+,-]',raw[0].lower().strip())
            # in case of a leading '-' or '+'
            if len(raw[0]) == 0:
                raw = raw[1:]
            # pnames = []
            # for r in raw:
            #     if '*' not in r:
            #         continue
            #     pname =  r.split('*')[1].replace("log(", '').replace(')', '').strip()
            #     pnames.append(pname)
            # return pnames
            return [r.split('*')[1].replace("log(",'').replace(')','').strip() for r in raw if '*' in r]

        self.prior_information.loc[:,"names"] =\
            self.prior_information.equation.apply(lambda x: parse(x))


    def add_pi_equation(self,par_names,pilbl=None,rhs=0.0,weight=1.0,
                        obs_group="pi_obgnme",coef_dict={}):
        """ a helper to construct a new prior information equation.

        Parameters
        ----------
        par_names : list
            parameter names in the equation
        pilbl : str
            name to assign the prior information equation.  If None,
            a generic equation name is formed. Default is None
        rhs : (float)
            the right-hand side of the equation
        weight : (float)
            the weight of the equation
        obs_group : str
            the observation group for the equation. Default is 'pi_obgnme'
        coef_dict : dict
            a dictionary of parameter name, coefficient pairs to assign
            leading coefficients for one or more parameters in the equation.
            If a parameter is not listed, 1.0 is used for its coefficients.
            Default is {}

        """
        if pilbl is None:
            pilbl = "pilbl_{0}".format(self.__pi_count)
            self.__pi_count += 1
        missing,fixed = [],[]

        for par_name in par_names:
            if par_name not in self.parameter_data.parnme:
                missing.append(par_name)
            elif self.parameter_data.loc[par_name,"partrans"] in ["fixed","tied"]:
                fixed.append(par_name)
        if len(missing) > 0:
            raise Exception("Pst.add_pi_equation(): the following pars "+\
                            " were not found: {0}".format(','.join(missing)))
        if len(fixed) > 0:
            raise Exception("Pst.add_pi_equation(): the following pars "+\
                            " were are fixed/tied: {0}".format(','.join(missing)))
        eqs_str = ''
        sign = ''
        for i,par_name in enumerate(par_names):
            coef = coef_dict.get(par_name,1.0)
            if coef < 0.0:
                sign = '-'
                coef = np.abs(coef)
            elif i > 0: sign = '+'
            if self.parameter_data.loc[par_name,"partrans"] == "log":
                par_name = "log({})".format(par_name)
            eqs_str += " {0} {1} * {2} ".format(sign,coef,par_name)
        eqs_str += " = {0}".format(rhs)
        self.prior_information.loc[pilbl,"pilbl"] = pilbl
        self.prior_information.loc[pilbl,"equation"] = eqs_str
        self.prior_information.loc[pilbl,"weight"] = weight
        self.prior_information.loc[pilbl,"obgnme"] = obs_group


    def rectify_pi(self):
        """ rectify the prior information equation with the current state of the
        parameter_data dataframe.  Equations that list fixed, tied or missing parameters
        are removed. This method is called during Pst.write()

        """
        if self.prior_information.shape[0] == 0:
            return
        self._parse_pi_par_names()
        adj_names = self.adj_par_names
        def is_good(names):
            for n in names:
                if n not in adj_names:
                    return False
            return True
        keep_idx = self.prior_information.names.\
            apply(lambda x: is_good(x))
        self.prior_information = self.prior_information.loc[keep_idx,:]

    def write(self,new_filename,update_regul=False):
        """write a pest control file

        Parameters
        ----------
        new_filename : str
            name of the new pest control file
        update_regul : (boolean)
            flag to update zero-order Tikhonov prior information
            equations to prefer the current parameter values

        """
        self._rectify_pgroups()
        self.rectify_pi()
        self._update_control_section()

        f_out = open(new_filename, 'w')
        f_out.write("pcf\n* control data\n")
        self.control_data.write(f_out)

        for line in self.other_lines:
            f_out.write(line)

        self.svd_data.write(f_out)

        f_out.write("* parameter groups\n")

        # to catch the byte code ugliness in python 3
        pargpnme = self.parameter_groups.loc[:,"pargpnme"].copy()
        self.parameter_groups.loc[:,"pargpnme"] = \
            self.parameter_groups.pargpnme.apply(self.pargp_format["pargpnme"])

        #self.parameter_groups.index = self.parameter_groups.pop("pargpnme")
        #gp_fieldnames = [name for name in self.pargp_fieldnames if name in self.parameter_groups.columns]
        if self.parameter_groups.isnull().values.any():
            warnings.warn("WARNING: NaNs in parameter_groups dataframe")
        f_out.write(self.parameter_groups.to_string(col_space=0,
                                                  formatters=self.pargp_format,
                                                  columns=self.pargp_fieldnames,
                                                  justify="right",
                                                  header=False,
                                                  index=False) + '\n')
        self.parameter_groups.loc[:,"pargpnme"] = pargpnme.values
        #self.parameter_groups.index = pargpnme

        if self.parameter_data.loc[:,pst_utils.pst_config["par_fieldnames"]].isnull().values.any():
            warnings.warn("WARNING: NaNs in parameter_data dataframe")

        f_out.write("* parameter data\n")
        #self.parameter_data.index = self.parameter_data.pop("parnme")
        f_out.write(self.parameter_data.to_string(col_space=0,
                                                  columns=self.par_fieldnames,
                                                  formatters=self.par_format,
                                                  justify="right",
                                                  header=False,
                                                  index=False) + '\n')
        #self.parameter_data.loc[:,"parnme"] = self.parameter_data.index

        if self.tied is not None:
            if self.tied.isnull().values.any():
                warnings.warn("WARNING: NaNs in tied dataframe")
            #self.tied.index = self.tied.pop("parnme")
            f_out.write(self.tied.to_string(col_space=0,
                                            columns=self.tied_fieldnames,
                                            formatters=self.tied_format,
                                            justify='right',
                                            header=False,
                                            index=False)+'\n')
            #self.tied.loc[:,"parnme"] = self.tied.index
        f_out.write("* observation groups\n")
        for group in self.obs_groups:
            try:
                group = group.decode()
            except:
                pass
            f_out.write(pst_utils.SFMT(str(group))+'\n')
        for group in self.prior_groups:
            try:
                group = group.decode()
            except:
                pass
            f_out.write(pst_utils.SFMT(str(group))+'\n')
        if self.observation_data.loc[:,pst_utils.pst_config["obs_fieldnames"]].isnull().values.any():
            warnings.warn("WARNING: NaNs in observation_data dataframe")
        f_out.write("* observation data\n")
        #self.observation_data.index = self.observation_data.pop("obsnme")
        f_out.write(self.observation_data.to_string(col_space=0,
                                                  formatters=self.obs_format,
                                                  columns=self.obs_fieldnames,
                                                  justify="right",
                                                  header=False,
                                                  index=False) + '\n')
        #self.observation_data.loc[:,"obsnme"] = self.observation_data.index

        f_out.write("* model command line\n")
        for cline in self.model_command:
            f_out.write(cline+'\n')

        f_out.write("* model input/output\n")
        for tplfle,infle in zip(self.template_files,self.input_files):
            f_out.write(tplfle+' '+infle+'\n')
        for insfle,outfle in zip(self.instruction_files,self.output_files):
            f_out.write(insfle+' '+outfle+'\n')

        if self.nprior > 0:
            if self.prior_information.isnull().values.any():
                print("WARNING: NaNs in prior_information dataframe")
            f_out.write("* prior information\n")
            #self.prior_information.index = self.prior_information.pop("pilbl")
            max_eq_len = self.prior_information.equation.apply(lambda x:len(x)).max()
            eq_fmt_str =  " {0:<" + str(max_eq_len) + "s} "
            eq_fmt_func = lambda x:eq_fmt_str.format(x)
            #  17/9/2016 - had to go with a custom writer loop b/c pandas doesn't want to
            # output strings longer than 100, even with display.max_colwidth
            #f_out.write(self.prior_information.to_string(col_space=0,
            #                                  columns=self.prior_fieldnames,
            #                                  formatters=pi_formatters,
            #                                  justify="right",
            #                                  header=False,
            #                                 index=False) + '\n')
            #self.prior_information["pilbl"] = self.prior_information.index
            for idx,row in self.prior_information.iterrows():
                f_out.write(pst_utils.SFMT(row["pilbl"]))
                f_out.write(eq_fmt_func(row["equation"]))
                f_out.write(pst_utils.FFMT(row["weight"]))
                f_out.write(pst_utils.SFMT(row["obgnme"]) + '\n')
        if self.control_data.pestmode.startswith("regul"):
            #f_out.write("* regularisation\n")
            #if update_regul or len(self.regul_lines) == 0:
            #    f_out.write(self.regul_section)
            #else:
            #    [f_out.write(line) for line in self.regul_lines]
            self.reg_data.write(f_out)

        for key,value in self.pestpp_options.items():
            f_out.write("++{0}({1})\n".format(str(key),str(value)))

        f_out.close()


    def get(self, par_names=None, obs_names=None):
        """get a new pst object with subset of parameters and/or observations

        Parameters
        ----------
        par_names : list
            a list of parameter names to have in the new Pst instance.
            If None, all parameters are in the new Pst instance. Default
            is None
        obs_names : list
            a list of observation names to have in the new Pst instance.
            If None, all observations are in teh new Pst instance. Default
            is None

        Returns
        -------
        Pst : Pst
            a new Pst instance

        """
        pass
        #if par_names is None and obs_names is None:
        #    return copy.deepcopy(self)
        if par_names is None:
            par_names = self.parameter_data.parnme
        if obs_names is None:
            obs_names = self.observation_data.obsnme

        new_par = self.parameter_data.copy()
        if par_names is not None:
            new_par.index = new_par.parnme
            new_par = new_par.loc[par_names, :]
        new_obs = self.observation_data.copy()
        new_res = None

        if obs_names is not None:
            new_obs.index = new_obs.obsnme
            new_obs = new_obs.loc[obs_names]
            if self.__res is not None:
                new_res = copy.deepcopy(self.res)
                new_res.index = new_res.name
                new_res = new_res.loc[obs_names, :]

        new_pargp = self.parameter_groups.copy()
        new_pargp.index = new_pargp.pargpnme
        new_pargp_names = new_par.pargp.value_counts().index
        new_pargp = new_pargp.loc[new_pargp_names,:]

        new_pst = Pst(self.filename, resfile=self.resfile, load=False)
        new_pst.parameter_data = new_par
        new_pst.observation_data = new_obs
        new_pst.parameter_groups = new_pargp
        new_pst.__res = new_res
        new_pst.prior_information = self.prior_information
        new_pst.rectify_pi()
        new_pst.control_data = self.control_data.copy()

        new_pst.model_command = self.model_command
        new_pst.template_files = self.template_files
        new_pst.input_files = self.input_files
        new_pst.instruction_files = self.instruction_files
        new_pst.output_files = self.output_files

        if self.tied is not None:
            print("Pst.get() warning: not checking for tied parameter " +
                  "compatibility in new Pst instance")
            new_pst.tied = self.tied.copy()
        new_pst.other_lines = self.other_lines
        new_pst.pestpp_options = self.pestpp_options
        new_pst.regul_lines = self.regul_lines

        return new_pst

    def zero_order_tikhonov(self,parbounds=True):
        raise Exception("Pst.zero_oder_tikhonov has moved to utils.helpers")


    def parrep(self, parfile=None,enforce_bounds=True):
        """replicates the pest parrep util. replaces the parval1 field in the
            parameter data section dataframe

        Parameters
        ----------
        parfile : str
            parameter file to use.  If None, try to use
            a parameter file that corresponds to the case name.
            Default is None
        enforce_hounds : bool
            flag to enforce parameter bounds after parameter values are updated.
            This is useful because PEST and PEST++ round the parameter values in the
            par file, which may cause slight bound violations

        """
        if parfile is None:
            parfile = self.filename.replace(".pst", ".par")
        par_df = pst_utils.read_parfile(parfile)
        self.parameter_data.index = self.parameter_data.parnme
        par_df.index = par_df.parnme
        self.parameter_data.parval1 = par_df.parval1
        self.parameter_data.scale = par_df.scale
        self.parameter_data.offset = par_df.offset

        if enforce_bounds:
            par = self.parameter_data
            idx = par.loc[par.parval1 > par.parubnd,"parnme"]
            par.loc[idx,"parval1"] = par.loc[idx,"parubnd"]
            idx = par.loc[par.parval1 < par.parlbnd,"parnme"]
            par.loc[idx, "parval1"] = par.loc[idx, "parlbnd"]




    def adjust_weights_recfile(self, recfile=None):
        """adjusts the weights by group of the observations based on the phi components
        in a pest record file so that total phi is equal to the number of
        non-zero weighted observations

        Parameters
        ----------
        recfile : str
            record file name.  If None, try to use a record file
            with the Pst case name.  Default is None

        """
        if recfile is None:
            recfile = self.filename.replace(".pst", ".rec")
        assert os.path.exists(recfile), \
            "Pst.adjust_weights_recfile(): recfile not found: " +\
            str(recfile)
        iter_components = pst_utils.get_phi_comps_from_recfile(recfile)
        iters = iter_components.keys()
        iters.sort()
        obs = self.observation_data
        ogroups = obs.groupby("obgnme").groups
        last_complete_iter = None
        for ogroup, idxs in ogroups.iteritems():
            for iiter in iters[::-1]:
                incomplete = False
                if ogroup not in iter_components[iiter]:
                    incomplete = True
                    break
                if not incomplete:
                    last_complete_iter = iiter
                    break
        if last_complete_iter is None:
            raise Exception("Pst.pwtadj2(): no complete phi component" +
                            " records found in recfile")
        self._adjust_weights_by_phi_components(
            iter_components[last_complete_iter])

    def adjust_weights_resfile(self, resfile=None):
        """adjusts the weights by group of the observations based on the phi components
        in a pest residual file so that total phi is equal to the number of
        non-zero weighted observations

        Parameters
        ----------
        resfile : str
            residual file name.  If None, try to use a residual file
            with the Pst case name.  Default is None

        """
        if resfile is not None:
            self.resfile = resfile
            self.__res = None
        phi_comps = self.phi_components
        self._adjust_weights_by_phi_components(phi_comps)

    def _adjust_weights_by_phi_components(self, components):
        """resets the weights of observations by group to account for
        residual phi components.

        Parameters
        ----------
        components : dict
            a dictionary of obs group:phi contribution pairs

        """
        obs = self.observation_data
        nz_groups = obs.groupby(obs["weight"].map(lambda x: x == 0)).groups
        ogroups = obs.groupby("obgnme").groups
        for ogroup, idxs in ogroups.items():
            if self.control_data.pestmode.startswith("regul") \
                    and "regul" in ogroup.lower():
                continue
            og_phi = components[ogroup]
            nz_groups = obs.loc[idxs,:].groupby(obs.loc[idxs,"weight"].\
                                                map(lambda x: x == 0)).groups
            og_nzobs = 0
            if False in nz_groups.keys():
                og_nzobs = len(nz_groups[False])
            if og_nzobs == 0 and og_phi > 0:
                raise Exception("Pst.adjust_weights_by_phi_components():"
                                " no obs with nonzero weight," +
                                " but phi > 0 for group:" + str(ogroup))
            if og_phi > 0:
                factor = np.sqrt(float(og_nzobs) / float(og_phi))
                obs.loc[idxs,"weight"] = obs.weight[idxs] * factor
        self.observation_data = obs

    def __reset_weights(self, target_phis, res_idxs, obs_idxs):
        """private method to reset weights based on target phi values
        for each group.  This method should not be called directly

        Parameters
        ----------
        target_phis : dict
            target phi contribution for groups to reweight
        res_idxs : dict
            the index positions of each group of interest
            in the res dataframe
        obs_idxs : dict
            the index positions of each group of interest
            in the observation data dataframe

        """

        for item in target_phis.keys():
            assert item in res_idxs.keys(),\
                "Pst.__reset_weights(): " + str(item) +\
                " not in residual group indices"
            assert item in obs_idxs.keys(), \
                "Pst.__reset_weights(): " + str(item) +\
                " not in observation group indices"
            actual_phi = ((self.res.loc[res_idxs[item], "residual"] *
                           self.observation_data.loc
                           [obs_idxs[item], "weight"])**2).sum()
            if actual_phi > 0.0:
                weight_mult = np.sqrt(target_phis[item] / actual_phi)
                self.observation_data.loc[obs_idxs[item], "weight"] *= weight_mult
            else:
                print("Pst.__reset_weights() warning: phi group {0} has zero phi, skipping...".format(item))

    def adjust_weights_by_list(self,obslist,weight):
        """reset the weight for a list of observation names.  Supports the
        data worth analyses in pyemu.Schur class

        Parameters
        ----------
        obslist : list
            list of observation names
        weight : (float)
            new weight to assign

        """

        obs = self.observation_data
        obs = self.observation_data
        if not isinstance(obslist,list):
            obslist = [obslist]
        obslist = [str(i).lower() for i in obslist]
        groups = obs.groupby([lambda x:x in obslist,
                             obs.weight.apply(lambda x:x==0.0)]).groups
        if (True,True) in groups:
            obs.loc[groups[True,True],"weight"] = weight

    def adjust_weights(self,obs_dict=None,
                              obsgrp_dict=None):
        """reset the weights of observation groups to contribute a specified
        amount to the composite objective function

        Parameters
        ----------
        obs_dict : dict
            dictionary of obs name,new contribution pairs
        obsgrp_dict : dict
            dictionary of obs group name,contribution pairs

        Note
        ----
        if all observations in a named obs group have zero weight, they will be
        assigned a non-zero weight so that the request phi contribution
        can be met.  Similarly, any observations listed in obs_dict with zero
        weight will also be reset

        """

        self.observation_data.index = self.observation_data.obsnme
        self.res.index = self.res.name

        if obsgrp_dict is not None:
            # reset groups with all zero weights
            obs = self.observation_data
            for grp in obsgrp_dict.keys():
                if obs.loc[obs.obgnme==grp,"weight"].sum() == 0.0:
                    obs.loc[obs.obgnme==grp,"weight"] = 1.0
            res_groups = self.res.groupby("group").groups
            obs_groups = self.observation_data.groupby("obgnme").groups
            self.__reset_weights(obsgrp_dict, res_groups, obs_groups)
        if obs_dict is not None:
            # reset obs with zero weight
            obs = self.observation_data
            for oname in obs_dict.keys():
                if obs.loc[oname,"weight"] == 0.0:
                    obs.loc[oname,"weight"] = 1.0

            res_groups = self.res.groupby("name").groups
            obs_groups = self.observation_data.groupby("obsnme").groups
            self.__reset_weights(obs_dict, res_groups, obs_groups)


    def proportional_weights(self, fraction_stdev=1.0, wmax=100.0,
                             leave_zero=True):
        """setup  weights inversely proportional to the observation value

        Parameters
        ----------
        fraction_stdev : float
            the fraction portion of the observation
            val to treat as the standard deviation.  set to 1.0 for
            inversely proportional
        wmax : float
            maximum weight to allow
        leave_zero : bool
            flag to leave existing zero weights

        """
        new_weights = []
        for oval, ow in zip(self.observation_data.obsval,
                            self.observation_data.weight):
            if leave_zero and ow == 0.0:
                ow = 0.0
            elif oval == 0.0:
                ow = wmax
            else:
                nw = 1.0 / (np.abs(oval) * fraction_stdev)
                ow = min(wmax, nw)
            new_weights.append(ow)
        self.observation_data.weight = new_weights

    def calculate_pertubations(self):
        """ experimental method to calculate finite difference parameter
        pertubations.  The pertubation values are added to the
        Pst.parameter_data attribute

        Note
        ----
        user beware!

        """
        self.build_increments()
        self.parameter_data.loc[:,"pertubation"] = \
            self.parameter_data.parval1 + \
            self.parameter_data.increment

        self.parameter_data.loc[:,"out_forward"] = \
            self.parameter_data.loc[:,"pertubation"] > \
            self.parameter_data.loc[:,"parubnd"]

        out_forward = self.parameter_data.groupby("out_forward").groups
        if True in out_forward:
            self.parameter_data.loc[out_forward[True],"pertubation"] = \
                    self.parameter_data.loc[out_forward[True],"parval1"] - \
                    self.parameter_data.loc[out_forward[True],"increment"]

            self.parameter_data.loc[:,"out_back"] = \
            self.parameter_data.loc[:,"pertubation"] < \
            self.parameter_data.loc[:,"parlbnd"]
            out_back = self.parameter_data.groupby("out_back").groups
            if True in out_back:
                still_out = out_back[True]
                print(self.parameter_data.loc[still_out,:],flush=True)

                raise Exception("Pst.calculate_pertubations(): " +\
                                "can't calc pertubations for the following "+\
                                "Parameters {0}".format(','.join(still_out)))

    def build_increments(self):
        """ experimental method to calculate parameter increments for use
        in the finite difference pertubation calculations

        Note
        ----
        user beware!

        """
        self.enforce_bounds()

        par_groups = self.parameter_data.groupby("pargp").groups
        inctype = self.parameter_groups.groupby("inctyp").groups
        for itype,inc_groups in inctype.items():
            pnames = []
            for group in inc_groups:
                pnames.extend(par_groups[group])
                derinc = self.parameter_groups.loc[group,"derinc"]
                self.parameter_data.loc[par_groups[group],"derinc"] = derinc
            if itype == "absolute":
                self.parameter_data.loc[pnames,"increment"] = \
                    self.parameter_data.loc[pnames,"derinc"]
            elif itype == "relative":
                self.parameter_data.loc[pnames,"increment"] = \
                    self.parameter_data.loc[pnames,"derinc"] * \
                    self.parameter_data.loc[pnames,"parval1"]
            elif itype == "rel_to_max":
                mx = self.parameter_data.loc[pnames,"parval1"].max()
                self.parameter_data.loc[pnames,"increment"] = \
                    self.parameter_data.loc[pnames,"derinc"] * mx
            else:
                raise Exception('Pst.get_derivative_increments(): '+\
                                'unrecognized increment type:{0}'.format(itype))

        #account for fixed pars
        isfixed = self.parameter_data.partrans=="fixed"
        self.parameter_data.loc[isfixed,"increment"] = \
            self.parameter_data.loc[isfixed,"parval1"]

    def add_transform_columns(self):
        """ add transformed values to the Pst.parameter_data attribute

        """
        for col in ["parval1","parlbnd","parubnd","increment"]:
            if col not in self.parameter_data.columns:
                continue
            self.parameter_data.loc[:,col+"_trans"] = (self.parameter_data.parval1 *
                                                          self.parameter_data.scale) +\
                                                         self.parameter_data.offset
            #isnotfixed = self.parameter_data.partrans != "fixed"
            islog = self.parameter_data.partrans == "log"
            self.parameter_data.loc[islog,col+"_trans"] = \
                self.parameter_data.loc[islog,col+"_trans"].\
                    apply(lambda x:np.log10(x))

    def enforce_bounds(self):
        """ enforce bounds violation resulting from the
        parameter pertubation calculations

        """
        too_big = self.parameter_data.loc[:,"parval1"] > \
            self.parameter_data.loc[:,"parubnd"]
        self.parameter_data.loc[too_big,"parval1"] = \
            self.parameter_data.loc[too_big,"parubnd"]

        too_small = self.parameter_data.loc[:,"parval1"] < \
            self.parameter_data.loc[:,"parlbnd"]
        self.parameter_data.loc[too_small,"parval1"] = \
            self.parameter_data.loc[too_small,"parlbnd"]


    @classmethod
    def from_io_files(cls,tpl_files,in_files,ins_files,out_files,pst_filename=None):
        """ create a Pst instance from model interface files. Assigns generic values for
        parameter info.  Tries to use INSCHEK to set somewhat meaningful observation
        values

        Parameters
        ----------
        tpl_files : list
            list of template file names
        in_files : list
            list of model input file names (pairs with template files)
        ins_files : list
            list of instruction file names
        out_files : list
            list of model output file names (pairs with instruction files)
        pst_filename : str
            name of control file to write.  If None, no file is written.
            Default is None

        Returns
        -------
        Pst : Pst

        Note
        ----
        calls pyemu.helpers.pst_from_io_files()

        """
        from pyemu import helpers
        return helpers.pst_from_io_files(tpl_files=tpl_files,in_files=in_files,
                                           ins_files=ins_files,out_files=out_files,
                                         pst_filename=pst_filename)

    def add_parameters(self,template_file,in_file,pst_path=None):
        """ add new parameters to a control file

        Parameters
        ----------
            tpl_file : str
                template file
            in_file : str
                model input file
            pst_path : str(optional)
                the path to append to the template_file and in_file in the control file.  If
                not None, then any existing path in front of the template or in file is split off
                and pst_path is prepended.  Default is None

        Returns
        -------
        new_par_data : pandas.DataFrame
            the data for the new parameters that were added

        Note
        ----
        populates the new parameter information with default values

        """
        assert os.path.exists(template_file)

        # get the parameter names in the template file
        parnme = pst_utils.parse_tpl_file(template_file)

        # find "new" parameters that are not already in the control file
        new_parnme = [p for p in parnme if p not in self.parameter_data.parnme]

        if len(new_parnme) == 0:
            raise Exception("no new parameters found in template file {0}".format(template_file))

        # extend parameter_data
        new_par_data = pst_utils.populate_dataframe(new_parnme,pst_utils.pst_config["par_fieldnames"],
                                                    pst_utils.pst_config["par_defaults"],
                                                    pst_utils.pst_config["par_dtype"])
        new_par_data.loc[new_parnme,"parnme"] = new_parnme
        self.parameter_data = self.parameter_data.append(new_par_data)

        if pst_path is not None:
            template_file = os.path.join(pst_path,os.path.split(template_file)[-1])
            in_file = os.path.join(pst_path, os.path.split(in_file)[-1])
        self.template_files.append(template_file)
        self.input_files.append(in_file)

        return new_par_data


    def add_parameters(self,template_file,in_file,pst_path=None):
        """ add new parameters to a control file

        Parameters
        ----------
            tpl_file : str
                template file
            in_file : str
                model input file
            pst_path : str(optional)
                the path to append to the template_file and in_file in the control file.  If
                not None, then any existing path in front of the template or in file is split off
                and pst_path is prepended.  Default is None

        Returns
        -------
        new_par_data : pandas.DataFrame
            the data for the new parameters that were added. If no new parameters are in the
            new template file, returns None

        Note
        ----
        populates the new parameter information with default values

        """
        assert os.path.exists(template_file)

        # get the parameter names in the template file
        parnme = pst_utils.parse_tpl_file(template_file)

        # find "new" parameters that are not already in the control file
        new_parnme = [p for p in parnme if p not in self.parameter_data.parnme]

        if len(new_parnme) == 0:
            warnings.warn("no new parameters found in template file {0}".format(template_file))
            new_par_data = None
        else:
            # extend pa
            # rameter_data
            new_par_data = pst_utils.populate_dataframe(new_parnme,pst_utils.pst_config["par_fieldnames"],
                                                        pst_utils.pst_config["par_defaults"],
                                                        pst_utils.pst_config["par_dtype"])
            new_par_data.loc[new_parnme,"parnme"] = new_parnme
            self.parameter_data = self.parameter_data.append(new_par_data)

        if pst_path is not None:
            template_file = os.path.join(pst_path,os.path.split(template_file)[-1])
            in_file = os.path.join(pst_path, os.path.split(in_file)[-1])
        self.template_files.append(template_file)
        self.input_files.append(in_file)

        return new_par_data


    def add_observations(self,ins_file,out_file,pst_path=None):
        """ add new parameters to a control file

        Parameters
        ----------
            ins_file : str
                instruction file
            out_file : str
                model output file
            pst_path : str(optional)
                the path to append to the instruction file and out file in the control file.  If
                not None, then any existing path in front of the template or in file is split off
                and pst_path is prepended.  Default is None

        Returns
        -------
        new_obs_data : pandas.DataFrame
            the data for the new observations that were added

        Note
        ----
        populates the new observation information with default values

        tries to run inschek to populate obsval with the current model output file values

        """
        assert os.path.exists(ins_file),"{0}, {1}".format(os.getcwd(),ins_file)

        # get the parameter names in the template file
        obsnme = pst_utils.parse_ins_file(ins_file)

        # find "new" parameters that are not already in the control file
        new_obsnme = [o for o in obsnme if o not in self.observation_data.obsnme]

        if len(new_obsnme) == 0:
            raise Exception("no new observations found in instruction file {0}".format(ins_file))

        # extend observation_data
        new_obs_data = pst_utils.populate_dataframe(new_obsnme,pst_utils.pst_config["obs_fieldnames"],
                                                    pst_utils.pst_config["obs_defaults"],
                                                    pst_utils.pst_config["obs_dtype"])
        new_obs_data.loc[new_obsnme,"obsnme"] = new_obsnme
        self.observation_data = self.observation_data.append(new_obs_data)

        if pst_path is not None:
            ins_file = os.path.join(pst_path,os.path.split(ins_file)[-1])
            out_file = os.path.join(pst_path, os.path.split(out_file)[-1])
        self.instruction_files.append(ins_file)
        self.output_files.append(out_file)

        df = pst_utils._try_run_inschek(ins_file,out_file)
        if df is not None:
            self.observation_data.loc[df.index,"obsval"] = df.obsval
            new_obs_data.loc[df.index,"obsval"] = df.obsval
        return new_obs_data

    def write_input_files(self):
        """writes model input files using template files and current parvals.
        just syntatic sugar for pst_utils.write_input_files()

        Note
        ----
            adds "parval1_trans" column to Pst.parameter_data that includes the
            effect of scale and offset

        """
        pst_utils.write_input_files(self)

    def get_res_stats(self,nonzero=True):
        """ get some common residual stats from the current obsvals,
        weights and grouping in self.observation_data and the modelled values in
        self.res.  The key here is 'current' because if obsval, weights and/or
        groupings have changed in self.observation_data since the res file was generated
        then the current values for obsval, weight and group are used

        Parameters
        ----------
            nonzero : bool
                calculate stats using only nonzero-weighted observations.  This may seem
                obsvious to most users, but you never know....

        Returns
        -------
            df : pd.DataFrame
                a dataframe with columns for groups names and indices of statistic name.

        Note
        ----
            the normalized RMSE is normalized against the obsval range (max - min)

        """
        res = self.res.copy()
        res.loc[:,"obsnme"] = res.pop("name")
        res.index = res.obsnme
        if nonzero:
            obs = self.observation_data.loc[self.nnz_obs_names,:]
        #print(obs.shape,res.shape)
        res = res.loc[obs.obsnme,:]
        #print(obs.shape, res.shape)

        #reset the res parts to current obs values and remove
        #duplicate attributes
        res.loc[:,"weight"] = obs.weight
        res.loc[:,"obsval"] = obs.obsval
        res.loc[:,"obgnme"] = obs.obgnme
        res.pop("group")
        res.pop("measured")

        #build these attribute lists for faster lookup later
        og_dict = {og:res.loc[res.obgnme==og,"obsnme"] for og in res.obgnme.unique()}
        og_names = list(og_dict.keys())

        # the list of functions and names
        sfuncs = [self._stats_rss, self._stats_mean,self._stats_mae,
                         self._stats_rmse,self._stats_nrmse]
        snames = ["rss","mean","mae","rmse","nrmse"]

        data = []
        for sfunc,sname in zip(sfuncs,snames):
            full = sfunc(res)
            groups = [full]
            for og in og_names:
                onames = og_dict[og]
                res_og = res.loc[onames,:]
                groups.append(sfunc(res_og))
            data.append(groups)

        og_names.insert(0,"all")
        df = pd.DataFrame(data,columns=og_names,index=snames)
        return df

    def _stats_rss(self,df):
        return (((df.modelled - df.obsval) * df.weight)**2).sum()

    def _stats_mean(self,df):
        return (df.modelled - df.obsval).mean()

    def _stats_mae(self,df):
        return ((df.modelled - df.obsval).apply(np.abs)).sum() / df.shape[0]

    def _stats_rmse(self,df):
        return np.sqrt(((df.modelled - df.obsval)**2).sum() / df.shape[0])

    def _stats_nrmse(self,df):
        return self._stats_rmse(df) / (df.obsval.max() - df.obsval.min())

