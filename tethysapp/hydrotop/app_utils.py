# from datetime import datetime
import subprocess, shlex, shutil

import os, sys, json
import numpy as np
# try:
#     from osgeo import ogr, osr
#     import fiona
# except Exception, e:
#     print e

from datetime import date
import datetime

# from django.shortcuts import render
# from django.contrib.auth.decorators import login_required
# from tethys_gizmos.gizmo_options import MapView, MVLayer, MVView
# from tethys_gizmos.gizmo_options import TextInput, DatePicker
# from tethys_sdk.gizmos import SelectInput
from tethys_sdk.gizmos import TimeSeries

from HDS_hydrogate_dev import HydroDS
import HDS_settings
HDS = HydroDS(username=HDS_settings.USER_NAME, password=HDS_settings.PASSWORD)


# import sys
# sys.path.append('/utils')
# from utils.pytopkapi_utils import *


import zipfile

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


def create_model_input_dict_from_request(request):
    # from the user input forms in model_input page, the request is converted to a dictionary of inputs
    print request.user.username
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    from django.conf import settings

    buffer_on_bbox_from_file = 0 # times the cell size
    test_string = 'None'
    wshed_tif_fname = None

    wshed_shp_fname = None
    outlet_shp_fname = None

    watershed_files = {}
    outlet_files = {}

    inputs_dictionary = {"user_name": request.user.username,
                         "simulation_name": request.POST['simulation_name'],
                         "simulation_folder":'',


                        "simulation_start_date": request.POST['simulation_start_date_picker'],
                         "simulation_end_date": request.POST['simulation_end_date_picker'],
                         "USGS_gage": str(request.POST['USGS_gage']),

                         "outlet_y": round(  float(request.POST['outlet_y']),6),
                         "outlet_x": round( float(request.POST['outlet_x']),6),
                         "box_topY": round( float(request.POST['box_topY']),6),
                         "box_bottomY": round( float(request.POST['box_bottomY']),6),
                         "box_rightX": round( float(request.POST['box_rightX']),6),
                         "box_leftX": round( float(request.POST['box_leftX']),6),

                         "timeseries_source": request.POST['timeseries_source'],

                         "threshold": int(request.POST['threshold']),
                         "cell_size": float(request.POST['cell_size']),
                         "timestep": int(request.POST['timestep']),
                         "model_engine": request.POST['model_engine']
                         }



    # # if the input is hydroshare id
    # if request.POST['outlet_hs']:
    #     pass #:todo
    # if request.POST['bounding_box_hs']:
    #     pass #:todo


    avg_lat = (inputs_dictionary['box_bottomY'] + inputs_dictionary['box_topY'])/2

    if request.is_ajax and request.method == 'POST' and request.FILES.getlist('watershed_upload') != []:

        for afile in request.FILES.getlist('watershed_upload'):

            print "watershed file(s) detected"

            tmp = os.path.join(settings.MEDIA_ROOT, "tmp", afile.name)
            path = default_storage.save(tmp, ContentFile(afile.read()))

            tmp_file = os.path.join(settings.MEDIA_ROOT, path)
            tmp_file = os.path.abspath(tmp_file)

            if os.path.split(tmp_file)[-1].split(".")[-1] == 'shp':
                watershed_files['shp'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'shx':
                watershed_files['shx'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'dbf':
                watershed_files['dbf'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'prj':
                watershed_files['prj'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] =='tif' or os.path.split(tmp_file)[-1].split(".")[-1]=='tiff':
                watershed_files['tif'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'zip':
                watershed_files['zip'] = tmp_file
            if os.path.split(tmp_file)[-1][-3:] not in ['shp', 'shx', 'dbf', 'prj', 'tif', 'tiff', 'zip']:
                os.remove(tmp_file)

        if 'shp' and 'shx' in watershed_files:
            print 'shapefiles detected..'
            wshed_shp_fname = rename_shapefile_collection(watershed_files, 'watershed')
            lon_e, lat_s, lon_w, lat_n = get_box_from_tif_or_shp(wshed_shp_fname)

        if 'zip' in watershed_files:
            print 'shapefile in zip, possibly..'
            lon_e, lat_s, lon_w, lat_n = get_box_from_tif_or_shp(watershed_files['zip'])

        if 'tif' in watershed_files:
            print 'tiff file detected..'
            lon_e, lat_s, lon_w, lat_n = get_box_from_tif_or_shp(watershed_files['tif'])
            # lon_e, lat_s, lon_w, lat_n = get_box_from_tif(watershed_files['tif'])


        # buffer for the bbox size(cell size)
        angle_along_lon, angle_along_lat = meter_to_degree(buffer_on_bbox_from_file* inputs_dictionary['cell_size'], avg_lat)
        print 'angle_along_lon, angle_along_lat', angle_along_lon, angle_along_lat

        # :TODO check if the region is valid

        # update input_dictionary
        inputs_dictionary['box_rightX'] = round(lon_e + angle_along_lon, 6)
        inputs_dictionary['box_bottomY'] = round(lat_s - angle_along_lat, 6)
        inputs_dictionary['box_leftX'] = round(lon_w - angle_along_lon, 6)
        inputs_dictionary['box_topY'] = round(lat_n + angle_along_lat, 6)

        # inputs_dictionary['box_topY'] = lat_n
        # inputs_dictionary['box_bottomY'] = lat_s
        # inputs_dictionary['box_rightX'] = lon_e
        # inputs_dictionary['box_leftX'] = lon_w
        # print  lon_e, lat_s, lon_w, lat_n


    if request.is_ajax and request.method == 'POST' and request.FILES.getlist('outlet_upload') != []:
        print "Outlet file(s) detected", request.FILES.getlist('outlet_upload')

        for afile in request.FILES.getlist('outlet_upload'):

            tmp = os.path.join(settings.MEDIA_ROOT, "tmp", afile.name)
            path = default_storage.save(tmp, ContentFile(afile.read()))

            tmp_file = os.path.join(settings.MEDIA_ROOT, path)
            tmp_file = os.path.abspath(tmp_file)
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'shp':
                outlet_files['shp'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'shx':
                outlet_files['shx'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'dbf':
                outlet_files['dbf'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] == 'prj':
                outlet_files['prj'] = tmp_file
            if os.path.split(tmp_file)[-1].split(".")[-1] =='tif' or os.path.split(tmp_file)[-1].split(".")[-1]=='tiff':
                outlet_files['tif'] = tmp_file
            if os.path.split(tmp_file)[-1][-3:] not in ['shp', 'shx', 'dbf', 'prj', 'tif', 'tiff']:
                os.remove(tmp_file)

        outlet_shp_fname = rename_shapefile_collection(outlet_files, 'outlet')

        if outlet_shp_fname != None:
            # get the outlet coordinate
            lon, lat = get_outlet_xy_from_shp(outlet_shp_fname + '.shp')

            # :TODO check if the outlet point is valid, and whether more than one point is given

            # update the input dictionary
            inputs_dictionary['outlet_x'], inputs_dictionary['outlet_y'] = round(lon, 6), round(lat, 6)


    if inputs_dictionary['model_engine'].lower() == 'topnet':
        inputs_dictionary['threshold_topnet'] = int(request.POST['threshold_topnet'])
        inputs_dictionary['pk_min_threshold'] = int(request.POST['pk_min_threshold'])
        inputs_dictionary['pk_max_threshold'] = int(request.POST['pk_max_threshold'])
        inputs_dictionary['pk_num_thershold'] = int(request.POST['pk_num_thershold'])


    return inputs_dictionary



def create_hydrograph(date_in_datetime, Qsim, simulation_name, error):
    # preparing timeseries data in the format shown in: http://docs.tethysplatform.org/en/latest/tethys_sdk/gizmos/plot_view.html#time-series
    from tethys_sdk.gizmos import TimeSeries

    hydrograph = []
    date_broken = [[dt.year, dt.month, dt.day, dt.hour, dt.minute] for dt in date_in_datetime]
    for i in range(len(Qsim)):
        date = datetime.datetime(year=date_broken[i][0], month=date_broken[i][1], day=date_broken[i][2], hour=date_broken[i][3],
                        minute=date_broken[i][4])
        hydrograph.append([date, float(Qsim[i])])

    observed_hydrograph = TimeSeries(
        height='500px',
        width='500px',
        engine='highcharts',
        title='Hydrograph ',
        subtitle="Simulated and Observed flow for " + simulation_name,
        y_axis_title='Discharge',
        y_axis_units='cumecs',
        series=[{
            'name': 'Simulated Flow',
            'data': hydrograph,
        }]
    )
    return observed_hydrograph

def create_1d(timeseries_list, label, unit):
    if timeseries_list == "" or timeseries_list==[]:
        return
    from tethys_sdk.gizmos import TimeSeries
    timeseries_obj = TimeSeries(
        height='200px', width='600px',
        engine='highcharts',
        title=label,
        inverted=True,
        # subtitle="Simulated and Observed flow  ",
        y_axis_title='',
        y_axis_units=unit,
        series=[{
            'name': 'Water level',
            'data': timeseries_list,
            'fillOpacity': 0.2,
        }])
    return  timeseries_obj


def read_hydrograph_from_txt(hydrograph_fname):

    ar = np.genfromtxt(hydrograph_fname, dtype=(int, int, int, int, int, float))
    hydrograph_series = []
    for i in range(len(ar)):
        date = datetime.datetime(year= int(ar[i][0]), month=int(ar[i][1]), day=int(ar[i][2]), hour=int(ar[i][3]),   minute=int(ar[i][4]))
        hydrograph_series.append([date, float(ar[i][5] ) ])

    return hydrograph_series

    # if hydrograph_series_fname == None:
    #     hydrograph_series_fname = '/home/prasanna/tethysdev/hydrologic_modeling/tethysapp/hydrologic_modeling/workspaces/user_workspaces/usr1/abebebsb323bsg1283bg3.txt'
    # hs_resource_id_created = os.path.basename(hydrograph_series_fname).split(".")[0]  # assuming the filename is the hydroshare resource ID
    #
    # # df = pd.read_csv(f, names=['year' , 'month' , 'day', 'hour', 'minute', 'q_obs', 'q_sim'])  # parse_dates=[0], infer_datetime_format=True
    # # # df2 = pd.read_csv(f, names=['date','q_obs', 'q_sim'], parse_dates=[0], infer_datetime_format=True)
    # # d = np.array(df['DateTime'])
    # # q_obs = np.array(df['q_obs'])
    # # q_sim = np.array(df['q_sim'])
    # # ar = zip(d, float(q_obs), float(q_sim))
    #
    # ar = np.genfromtxt(hydrograph_series_fname, delimiter="\t")
    # hydrograph_series = []
    # for i in range(len(ar)):
    #     date = datetime(year= int(ar[i][0]), month=int(ar[i][1]), day=int(ar[i][2]), hour=int(ar[i][3]),   minute=int(ar[i][4]))
    #     hydrograph_series.append([date, float(ar[i][5]),  float(ar[i][6])])
    #
    # return hydrograph_series, hs_resource_id_created


def read_data_from_json(json_fname):
    with open(json_fname) as json_file:
        data = json.load(json_file)
        try:
            hs_resource_id_created = data['hs_res_id_created']
        except:
            hs_resource_id_created = None

        calib_parameter = None
        numeric_param = None
        watershed_area = None

        nash_value = ''
        r2_value = ''
        errors = {}

        hydrograph_series_sim = []
        hydrograph_series_obs = []
        eta = []
        vs = []
        vc = []
        vo = []
        ppt = []
        ppt_cum = []  # cumulative
        eta_cum = []
        q_obs_cum = []
        q_sim_cum = []
        qsim_sum = 0
        eta_sum= 0
        ppt_sum = 0
        qobs_sum = 0

        def float2(num):
            try:
                num2 = float(num)
                if np.isnan(num2):
                    return 0
                else:
                    return float(num)
            except:
                return 0

        # also accomodate discharge in mm if area of watershed is provided
        if 'watershed_area' in data:
            watershed_area = data['watershed_area']
            cfs_2_mm = 0.028317 * 3600 * 24 / watershed_area * 1000.0  # mm of water releasing the system per day

            qobs_sum = 0
            qsim_sum = 0
            eta_sum = 0
            ppt_sum = 0

        if 'observed_discharge' in data:
            yr_mon_day_hr_min_discharge_list = data['observed_discharge']

            for yr, mon, day, hr, min, q in yr_mon_day_hr_min_discharge_list:
                date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                hydrograph_series_obs.append([date, float2(q)])

                if 'watershed_area' in data:
                    qobs_sum = qobs_sum + float2(q) * cfs_2_mm
                    q_obs_cum.append([date, qobs_sum])

        if 'ppt' in data:
            yr_mon_day_hr_min_ppt = data['ppt']

            for yr, mon, day, hr, min, val in yr_mon_day_hr_min_ppt:
                date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                ppt.append([date, float2(val)])

                if 'watershed_area' in data:
                    ppt_sum = ppt_sum + float2(val)
                    ppt_cum.append([date, ppt_sum])

        if 'runs' in data:
            if 'simulated_discharge' in data['runs'][-1]:
                yr_mon_day_hr_min_discharge_list = data['runs'][-1]['simulated_discharge']  # of the last run
                for yr, mon, day, hr, min, q in yr_mon_day_hr_min_discharge_list:
                    date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                    hydrograph_series_sim.append([date, float2(q)])
                    if 'watershed_area' in data:
                        qsim_sum = qsim_sum + float2(q) * cfs_2_mm
                        q_sim_cum.append([date, qsim_sum])

                hydrograph_series_sim = [[item[0], 0] if np.isnan(item[-1]) else item for item in hydrograph_series_sim]  # replace nan to 0

            if 'et_a' in data['runs'][-1]:
                yr_mon_day_hr_min_eta = data['runs'][-1]['et_a']
                for yr, mon, day, hr, min, val in yr_mon_day_hr_min_eta:
                    date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))

                    eta.append([date, float2(val)])

                    if 'watershed_area' in data:
                        eta_sum = eta_sum + float2(val)
                        eta_cum.append([date, eta_sum])

                eta = [[item[0], 0] if np.isnan(item[-1]) else item for item in eta]  # replace nan to 0


            if 'vc' in data['runs'][-1]:
                yr_mon_day_hr_min_eta = data['runs'][-1]['vc']
                for yr, mon, day, hr, min, val in yr_mon_day_hr_min_eta:
                    date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                    vc.append([date, float2(val)])
                vc = [[item[0], 0] if np.isnan(item[-1]) else item for item in vc]  # replace nan to 0

            if 'vs' in data['runs'][-1]:
                yr_mon_day_hr_min_eta = data['runs'][-1]['vs']
                for yr, mon, day, hr, min, val in yr_mon_day_hr_min_eta:
                    date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                    vs.append([date, float2(val)])
                vs = [[item[0], 0] if np.isnan(item[-1]) else item for item in vs]  # replace nan to 0

            if 'vo' in data['runs'][-1]:
                yr_mon_day_hr_min_eta = data['runs'][-1]['vo']
                for yr, mon, day, hr, min, val in yr_mon_day_hr_min_eta:
                    date = datetime.datetime(year=int(yr), month=int(mon), day=int(day), hour=int(hr), minute=int(min))
                    vo.append([date, float2(val)])
                vo = [[item[0], 0] if np.isnan(item[-1]) else item for item in vo]  # replace nan to 0

            # read numeric and calib parameters:
            try:
                # calib_parameter= {"fac_l": 1.0, "fac_n_o": 1.0, "fac_n_c": 1.0, "fac_th_s": 1.0, "fac_ks": 1.0},
                # numeric_param= {"pvs_t0": 50, "vo_t0": 750.0, "qc_t0": 0.0, "kc": 1.0},
                calib_parameter = data['runs'][-1]['calib_parameter']
                numeric_param = data['runs'][-1]['numeric_param']

            except:
                calib_parameter = None
                numeric_param = None

            # read error parameters:
            try:
                errors = data['runs'][-1]['errors']
                r2_value = data['runs'][-1]['errors']['r2_value']
                nash_value = data['runs'][-1]['errors']['nash_value']

            except:
                calib_parameter = None
                numeric_param = None

    return_dict = {'hs_res_id_created': hs_resource_id_created,
                   'hydrograph_series_obs': hydrograph_series_obs,
                   'hydrograph_series_sim': hydrograph_series_sim,
                   'eta': eta, 'vs': vs, 'vo': vo, 'vc': vc, 'ppt': ppt,
                   'calib_parameter': calib_parameter,'numeric_param': numeric_param,
                   'ppt_cum': ppt_cum, 'eta_cum': eta_cum, 'q_obs_cum': q_obs_cum, 'q_sim_cum': q_sim_cum,
                   'watershed_area':watershed_area, 'errors':errors, 'r2_value':r2_value, 'nash_value':nash_value, }

    # for key in return_dict:
    #     if key == 'hs_res_id_created':
    #         print str(key) + str(type(return_dict[key]))
    #
    #     elif key == 'numeric_param' or key == 'calib_parameter':
    #         print str(key) + str(return_dict[key])
    #     else:
    #         print str(key) + " : Length = " + str(len(return_dict[key]))
    return return_dict


def read_both_hydrograph_from_txt(hydrograph_fname):

    ar = np.genfromtxt(hydrograph_fname, dtype=(int, int, int, int, int, float, float))
    obs_hydrograph_series = []
    sim_hydrograph_series = []

    for i in range(len(ar)):
        date = datetime.datetime(year= int(ar[i][0]), month=int(ar[i][1]), day=int(ar[i][2]), hour=int(ar[i][3]),   minute=int(ar[i][4]))
        sim_hydrograph_series.append([date, float(ar[i][5] ) ])
        obs_hydrograph_series.append([date, float(ar[i][6])])

    return sim_hydrograph_series, obs_hydrograph_series

    # if hydrograph_series_fname == None:
    #     hydrograph_series_fname = '/home/prasanna/tethysdev/hydrologic_modeling/tethysapp/hydrologic_modeling/workspaces/user_workspaces/usr1/abebebsb323bsg1283bg3.txt'
    # hs_resource_id_created = os.path.basename(hydrograph_series_fname).split(".")[0]  # assuming the filename is the hydroshare resource ID
    #
    # # df = pd.read_csv(f, names=['year' , 'month' , 'day', 'hour', 'minute', 'q_obs', 'q_sim'])  # parse_dates=[0], infer_datetime_format=True
    # # # df2 = pd.read_csv(f, names=['date','q_obs', 'q_sim'], parse_dates=[0], infer_datetime_format=True)
    # # d = np.array(df['DateTime'])
    # # q_obs = np.array(df['q_obs'])
    # # q_sim = np.array(df['q_sim'])
    # # ar = zip(d, float(q_obs), float(q_sim))
    #
    # ar = np.genfromtxt(hydrograph_series_fname, delimiter="\t")
    # hydrograph_series = []
    # for i in range(len(ar)):
    #     date = datetime(year= int(ar[i][0]), month=int(ar[i][1]), day=int(ar[i][2]), hour=int(ar[i][3]),   minute=int(ar[i][4]))
    #     hydrograph_series.append([date, float(ar[i][5]),  float(ar[i][6])])
    #
    # return hydrograph_series, hs_resource_id_created


def create_model_input_dict_from_db( user_name=None , hs_resource_id=None, model_input_id=None ):
    """
    A function that creates input dictionary by querin the db. Accepts either hs_resource_id, or model_input_id to create
    the input dicitonary.
    :param model_inputs_table_id:  primary key id for the model_input table
    :param hs_resource_id:         Hydroshare resource id for the model_input table
    :param user_name:           tethys or hydroshare username
    :return:                    dictionary of input parameters
    """
    from .model import  SessionMaker, model_inputs_table
    from sqlalchemy import and_
    session = SessionMaker()

    # # IMPORTENT STEP: retrieve the model_inputs_table.id of this entry to pass it to the next page (calibration page)
    # current_model_inputs_table_id = str(len(session.query(model_inputs_table).filter(
    #     model_inputs_table.user_name == user_name).all()))  # because PK is the same as no of rows, i.e. length
    # print 'model_input ID for last sim, which will be used for calibration: ', current_model_inputs_table_id

    # # If passing to calibration is not our aim, we take the id as user input
    print 'MSG: model_input ID for which rest of the inputs are being retrieved: ', hs_resource_id

    if hs_resource_id != None:
        all_rows = session.query(model_inputs_table). \
            filter(and_(model_inputs_table.hs_resource_id == hs_resource_id,
                        model_inputs_table.user_name == user_name)).all()

    if model_input_id != None:
        all_rows = session.query(model_inputs_table).\
            filter(and_(model_inputs_table.id== model_input_id, model_inputs_table.user_name == user_name)).all()

    # :TODO for a particular user_name also requird. Can be poorly achieved by writing if-clause in for-loop below


    # retrieve the parameters and write to a dictionary
    inputs_dictionary = {}

    for row in all_rows:
        inputs_dictionary['id'] = row.id
        inputs_dictionary['user_name'] = row.user_name
        inputs_dictionary['simulation_name'] = row.simulation_name
        inputs_dictionary['simulation_folder'] = row.hs_resource_id
        inputs_dictionary['simulation_start_date'] = row.simulation_start_date
        inputs_dictionary['simulation_end_date'] = row.simulation_end_date
        inputs_dictionary['USGS_gage'] = row.USGS_gage

        inputs_dictionary['outlet_x'] = row.outlet_x
        inputs_dictionary['outlet_y'] = row.outlet_y
        inputs_dictionary['box_topY'] = row.box_topY
        inputs_dictionary['box_bottomY'] = row.box_bottomY
        inputs_dictionary['box_rightX'] = row.box_rightX
        inputs_dictionary['box_leftX'] = row.box_leftX

        timeseries_source, threshold, cell_size, timestep = row.other_model_parameters.split("__")
        inputs_dictionary['timeseries_source'] = timeseries_source
        inputs_dictionary['threshold'] = threshold
        inputs_dictionary['cell_size'] = cell_size
        inputs_dictionary['timestep'] = timestep

        inputs_dictionary['remarks'] = row.remarks
        inputs_dictionary['user_option'] = row.user_option
        inputs_dictionary['model_engine'] = row.model_engine


    print 'MSG: SUCCESS Querrying the database to create dictionary '
    if inputs_dictionary == {}:
        print "MSG: ERROR, HydroShare resource ID invalid!!! "

    return  inputs_dictionary

def create_simulation_list_after_querying_db(given_user_name=None, return_hs_resource_id=True, return_model_input_id = False):
    # returns a tethys gizmo or a drop down list, which should be referenced in html with name = 'simulation_names_list'
    # if return_hs_resource_id == True,
    from .model import engine, SessionMaker, Base, model_inputs_table ,model_calibration_table, model_result_table
    from tethys_sdk.gizmos import SelectInput

    Base.metadata.create_all(engine)    # Create tables
    session = SessionMaker()            # Make session

    #  # Query DB
    # simulations_queried = session.query(model_inputs_table).filter(model_inputs_table.user_name==given_user_name).all() # searches just the id input in URL

    # print 'Total no of records in model input table is', session.query(model_inputs_table).count()
    # print 'Total no of records in model calibration table is', session.query(model_calibration_table).count()
    # print 'Total no of records in model result table is', session.query(model_result_table).count()

    simulation_names_list_queried = []
    simulation_names_id = []
    hs_resourceID = []
    queries = []

    try:
        # Query DB
        simulations_queried = session.query(model_inputs_table).filter(
            model_inputs_table.user_name == given_user_name).all()  # searches just the id input in URL


        for record in simulations_queried:
            simulation_names_list_queried.append(record.simulation_name)
            simulation_names_id.append(record.id)
            hs_resourceID.append(record.hs_resource_id)


        if return_model_input_id :
            queries = zip(simulation_names_list_queried,simulation_names_id ) # returns model_input_table_id
        if return_hs_resource_id :
            queries = zip(simulation_names_list_queried, hs_resourceID)  # returns hs_resource of model instance

        if len(queries)<= 1:
            print 'Error in reading database, length only 1'
            stop
        print '**************Success: Querying the db to create a list of existing simulation'

    except Exception,e:
        queries = [( 'No saved model', '44248166e239490383f23f6568de5fcf')]
        print '**************Warning: Could not query the db to create a list of existing simulation. Error = >',e

    simulation_names_list = SelectInput(display_text='Saved Models',
                                     name='simulation_names_list',
                                     multiple=False,
                                     options= queries  )#[ (  simulations_queried[0].id, '1'),  (  simulations_queried[1].simulation_name, '2'  ),  (   simulations_queried[1].user_name, '2'  )]

    return simulation_names_list


def get_box_from_tif_or_shp(fname):

    if fname.split(".")[-1] == 'tif' or fname.split(".")[-1] == 'tiff':
        raster_request = HDS.upload_file(fname)
        output_json = os.path.split(fname)[0] + '/tif_json.txt'
        responseJSON = HDS.bboxfromtiff(raster_request, output_json='responseJSON.txt', save_as=output_json)

    if fname.split(".")[-1] == 'zip': # or fname.split(".")[-1] == 'zip':
        shp_request = HDS.upload_file(fname)
        output_json = os.path.split(fname)[0] + '/shp_json.txt'
        responseJSON = HDS.bboxfromshp(shp_request, output_json='responseJSON.txt', save_as=output_json)

    with open(output_json , 'r') as f:
        json_data = json.load(f)

    print 'json form raster: ', json_data

    maxx = json_data['maxx']
    miny= json_data['miny']
    minx=json_data['minx']
    maxy =json_data['maxy']

    return maxx, miny, minx, maxy


def meter_to_degree(distance_in_m, avg_lat):
    import math
    R = 6371000

    angle_along_lat = abs(distance_in_m / R * 180 / 3.14)                                 # in degree
    angle_along_lon = abs(distance_in_m / (R * math.cos(avg_lat*3.14/180.)) * 180 / 3.14) # in degree

    return angle_along_lon, angle_along_lat

    # edit geojson
    def json_to_js_prepend(json_filename):
        import fileinput

        # STEP1: add ) at the last line
        geojson_file = file(json_filename, 'a')
        geojson_file.write(')')
        geojson_file.close()

        # STEP2: add in the beginning based on http://stackoverflow.com/questions/5914627/prepend-line-to-beginning-of-a-file
        f = fileinput.input(json_filename, inplace=1)
        line_to_prepend = 'geojson_callback('
        for xline in f:
            if f.isfirstline():
                print line_to_prepend.rstrip('\r\n') + '\n' + xline,
            else:
                print xline,


def shapefile_to_geojson(path_to_shp):
    #input: Shapefile
    #output: geojson that the javascript can plot

    # shapefile to geojson using gdal
    directory, filename = os.path.split(path_to_shp)
    directory = '.'  #:todo del this line
    path_to_geojson = os.path.join(directory, "watershed_converted.geojson")
    cmd = '''ogr2ogr -f GeoJSON -t_srs crs:84 %s %s'''%(path_to_geojson, path_to_shp)
    print cmd
    os.system(cmd)
    return  path_to_geojson


    json_to_js_prepend(path_to_geojson)
    return path_to_geojson


def pull_from_hydroshare(hs_resource_id=None, output_folder=None):
    """
    :param hs_resource_id:      hydroshare resource id for public dataset(??), that contains a single shapefile
    :return: hs_to_shp:         {'outshp_path': path of shapefile (point or polygon) based on hs_resource_id, 'error':}
    """
    from hs_restclient import HydroShare, HydroShareAuthBasic

    # :TODO this password and user name should be User's
    auth = HydroShareAuthBasic(username='prasanna310', password='Hydrology12!@')
    hs = HydroShare(auth=auth)

    contains_pytopkapi_file = False
    pytopkapi_files = {}
    data_folder = os.path.join(output_folder, hs_resource_id, hs_resource_id, 'data', 'contents')


    resource = hs.getResource(pid=hs_resource_id, destination=output_folder, unzip=True, wait_for_bag_creation=False)

    files = [f for f in os.listdir(data_folder) if os.path.isfile(os.path.join(data_folder, f))]
    shp = [os.path.join(data_folder, f) for f in files if f.endswith('.shp')]
    tiff = [os.path.join(data_folder, f) for f in files if f.endswith('.tif')]

    ini = [f for f in files if f.endswith('.ini')]
    dat = [f for f in files if f.endswith('.dat')]
    h5 = [f for f in files if f.endswith('.h5')]

    if ('TOPKAPI.ini' in ini) and ('cell_param.dat' and 'global_param.dat' in dat) and ('rainfields.h5' and 'ET.h5' in h5):
        contains_pytopkapi_file = True
        pytopkapi_files= files


    return_dict = {'files':files, 'shp':shp, 'tiffs':tiff, 'contains_pytopkapi_file':contains_pytopkapi_file, 'pytopkapi_files':pytopkapi_files}

    return return_dict


def push_topnet_to_hydroshare(simulation_name=None, data_folder=None,  hs_usr_name=None, hs_password=None, hs_client_id=None, hs_client_secret=None, token=None):
    # sys.path.append('/home/prasanna/Documents/hydroshare-jupyterhub-master/notebooks/utilities')
    print ('Progress --> Pushing files to HydroShare. This could take a while...')
    # from hs_restclient import HydroShare, HydroShareAuthBasic
    #
    # auth = HydroShareAuthBasic(username=hs_usr_name, password=hs_password)
    # hs = HydroShare(auth=auth)
    from hs_restclient import HydroShare, HydroShareAuthBasic, HydroShareAuthOAuth2
    # create resource

    if hs_client_id != None and hs_client_secret != None and token != None:
        token = json.loads(token)
        auth = HydroShareAuthOAuth2(hs_client_id, hs_client_secret, token=token)
        hs = HydroShare(auth=auth, hostname='www.hydroshare.org')

    elif hs_usr_name != None and hs_password != None:
        auth = HydroShareAuthBasic(hs_usr_name, hs_password)
        hs = HydroShare(auth=auth, hostname='www.hydroshare.org')
    else:
        auth = HydroShareAuthBasic(username='topkapi_app', password='topkapi12!@')
        hs = HydroShare(auth=auth)

        # return {'success': "False",
        #         'message': "Authentication to HydroShare is failed. Please provide HydroShare User information"}


    abstract = 'Input-files for TOPNET model '  # abstract for the new resource
    title = 'Input-files for TOPNET model for ' + simulation_name  # title for the new resource
    keywords = ['TOPNET', 'Hydrologic_modeling', 'USU', 'HydroTOP']  # keywords for the new resource
    rtype = 'GenericResource'  # Hydroshare resource type
    files = [os.path.join(data_folder, f) for f in os.listdir(data_folder) if
             os.path.isfile(os.path.join(data_folder, f))]

    hs_res_id_created = hs.createResource(resource_type=rtype, title=title, resource_file=files[0],
                                          resource_filename=os.path.basename(files[0]),
                                          abstract=abstract, keywords=keywords,
                                          edit_users=None, view_users=None, edit_groups=None, view_groups=None,
                                          metadata=None, extra_metadata=None, progress_callback=None)
    print ('Resources created is ', hs_res_id_created)

    for file in files[1:]:
        var2 = hs.addResourceFile(hs_res_id_created, resource_file=file, resource_filename=os.path.basename(file),
                                  progress_callback=None)
        # print ('Resources created to which file %s added is %s', (file ,hs_res_id_created))

    try:
        hs.setAccessRules(hs_res_id_created, public=True)
    except:
        print ('Progress --> Failed to make the  hs resource public')
    print ('Progress --> Successfully pushed files to HydroShare. Created HS_res_ID ', hs_res_id_created)
    return hs_res_id_created

def read_raster(rast_fname, file_format='GTiff'):
    """Read the data in a raster file

    Parameters
    ----------
    rast_fname : string
        The path to the raster file.
    file_format : string
        The file format of the raster file, currently this can only be
        GeoTIFF ('GTiff' - default).

    Returns
    -------
    data : Numpy ndarray
        The 2D raster data in a Numpy array. The dtype of the returned
        array is the same as the data type stored in the raster file.

    """
    data = None
    if file_format != 'GTiff':
        err_str = 'Reading %s files not implemented.' % file_format
        raise NotImplementedError(err_str)
    else:
        try:
            from osgeo import gdal
            dset = gdal.Open(rast_fname)
            data = dset.ReadAsArray()
        except:
            pass

    return data

def create_hs_resources_from_hydrodslinks(list_of_hydrods_links, hs_usr_name, hs_paswd):

    # HydroDS created files upload



    # **************** USER UPLOADS, or BLANK UPLOADS *************
    workingDir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "utils/TOPNET")
    # need to upload biunry flow data
    # need to copy rainweights.txt as interpweight,dat
    # other wise it will not work
    # #### upload wind file - there is no wind data in Daymet
    HDS.upload_file(os.path.join(workingDir, "wind.dat"))
    # upload topnet control and watermangement files
    HDS.upload_file(os.path.join(workingDir, "topinp.dat"))
    HDS.upload_file(os.path.join(workingDir, "snowparam.dat"))
    HDS.upload_file(os.path.join(workingDir, "snow.in"))
    HDS.upload_file(os.path.join(workingDir, "modelspc.dat"))
    ##upload water management files
    HDS.upload_file(os.path.join(workingDir, "MeasuredFlowInfo.txt"))
    HDS.upload_file(os.path.join(workingDir, "MonthlyDemandFraction.txt"))
    HDS.upload_file(os.path.join(workingDir, "bcpar.dat"))
    HDS.upload_file(os.path.join(workingDir, "dc.dat"))
    HDS.upload_file(os.path.join(workingDir, "rainfill.txt"))
    HDS.upload_file(os.path.join(workingDir, "Reservoir.txt"))
    HDS.upload_file(os.path.join(workingDir, "ReturnFlow.txt"))
    HDS.upload_file(os.path.join(workingDir, "Rights.txt"))
    HDS.upload_file(os.path.join(workingDir, "SeasonsDefn.txt"))
    HDS.upload_file(os.path.join(workingDir, "Source.txt"))
    HDS.upload_file(os.path.join(workingDir, "SourceMixing.txt"))
    HDS.upload_file(os.path.join(workingDir, "user.txt"))
    HDS.upload_file(os.path.join(workingDir, "WatermgmtControl.txt"))

    topnet_inputPackage_dict = ['topinp.dat', 'snowparam.dat', 'modelspc.dat', 'bcpar.dat', 'dc.dat', 'wind.dat',
                                'rain.dat', 'clipar.dat', 'tmaxtmintdew.dat', 'streamflow_calibration.dat',
                                'rchproperties.txt', 'rchlink.txt', 'rchareas.txt', 'nodelinks.txt', 'distribution.txt',
                                'rainweights.txt', 'latlongfromxy.txt', 'basinpars.txt',
                                'MonthlyDemandFraction.txt', 'MeasuredFlowInfo.txt', 'WatermgmtControl.txt', 'user.txt',
                                'SourceMixing.txt', 'Source.txt', 'rainfill.txt',
                                'SeasonsDefn.txt', 'Rights.txt', 'ReturnFlow.txt', 'Reservoir.txt']

    # zip_files_result = HDS.zip_files(files_to_zip=topnet_inputPackage_dict, zip_file_name='topenet'+'.zip')
    #### save UEB input package as HydroShare resource
    hs_title = 'TOPNET input package for the watershed'
    hs_abstract = hs_title + 'It was created by the CI-WATER HydroDS'
    hs_keywords = ['HydroShare', 'HydroDS', 'DEM']
    HDS.set_hydroshare_account(username=HDS_settings.USER_NAME, password=HDS_settings.PASSWORD)
    HDS.create_hydroshare_resource(file_name='topnet.zip', resource_type='GenericResource', title=hs_title,
                                   abstract=hs_abstract, keywords=hs_keywords)
    # print('Finished TOPNET input setup')

def plot_multiseries_hydrograph(obs_q=None, sim_q=None):

    multi_timeseries_plot = TimeSeries(
        height='500px',
        width='500px',
        engine='highcharts',
        title='Multiple Timeseries Plot',
        y_axis_title='Snow depth',
        y_axis_units='m',
        series=[{
            'name': 'Observed',
            'data': obs_q  # I switched these so that the shorter series was in front of the larger
        }, {
            'name': 'Simulated',
            'data': sim_q
        }]
    )

    return multi_timeseries_plot


def validate_inputs(request):
    """

    :param                  : HTTP request
    :return:
        Validation status   :True if valid form, False if something wrong with the form
        Form Error          :If there is something wrong, gives a superficial error message
        inputs_dictionary   :If form is complete, returns the list of inputs as a dictionary
    """

    # defaults
    error_msg = ""
    inputs = {}
    inputs_dictionary = {}
    geojson_files = {}

    # All these inputs should go in the validation functions itself, not here in the front


    outlet_y = float(request.POST['outlet_y'])
    outlet_x = float(request.POST['outlet_x'])
    box_topY = float(request.POST['box_topY'])
    box_bottomY = float(request.POST['box_bottomY'])
    box_rightX = float(request.POST['box_rightX'])
    box_leftX = float(request.POST['box_leftX'])

    # # If UEB, TOPNET or RHESSys, print "Not ready yet"
    # if request.POST['timeseries_source'] != "Daymet":
    #     error_msg = "Time series you selected is not ready yet"

    if request.POST['model_engine'] != "TOPKAPI":
        error_msg = "Error 1: " + "Model you selected is not ready yet"
        validation_status = False

    # # Check Validity of USGS gage

    # # From RADIO BOX (not created so far), make sure inputs is read here so no IF required

    # # Ask confirmation of shapefile inputs
    shapefile_radio = True
    if shapefile_radio:
        # get the outlet x,y and the bounding box
        try:
            # because shp files are more than one, we interate
            for afile in request.FILES.getlist('outlet_shp'):

                if afile.name.split(".")[-1] == "shp":
                    outlet_shp = afile
                if afile.name.split(".")[-1] == "shx":
                    outlet_shx = afile
                if afile.name.split(".")[-1] == "prj":
                    outlet_prj = afile
                if afile.name.split(".")[-1] == "dbf":
                    outlet_dbf = afile

            outlet_x, outlet_y = get_outlet_xy_from_shp(shp_file=outlet_shp, shx_file=outlet_shx)
            geojson_files['geojson_outlet'] = shapefile_to_geojson(outlet_shp)



        except Exception, e:
            error_msg = "Error 2: " + str(e)
            validation_status = False

        try:
            for afile in request.FILES.getlist('watershed_shp'):

                if afile.name.split(".")[-1] == "shp":
                    watershed_shp = afile
                if afile.name.split(".")[-1] == "shx":
                    watershed_shx = afile
                if afile.name.split(".")[-1] == "prj":
                    watershed_prj = afile
                if afile.name.split(".")[-1] == "dbf":
                    watershed_dbf = afile

            # lines below are not being executed
            # box_rightX, box_bottomY, box_leftX, box_topY = get_box_xyxy_from_shp_shx(shp_file=watershed_shp,shx_file=watershed_shx)
            geojson_files['geojson_domain'] = shapefile_to_geojson(watershed_shp)


        except Exception, e:
            error_msg = "Error 3: " + str(e)
            validation_status = False

    # domain validation, make sure this contains US
    if not -90.0 < outlet_y < 90.0:
        error_msg = "Error 4: " + 'Outlet shapefile should be in WGS 84 coordinate system'
        validation_status = False
    if not -180.0 < outlet_x < 180.0:
        error_msg = "Error 4: " + 'Outlet shapefile should be in WGS 84 coordinate system'
        validation_status = False

    if not -90.0 < box_bottomY < 90.0:
        error_msg = "Error 5: " + 'Watershed shapefile should be in WGS 84 coordinate system'
        validation_status = False

    if not -180.0 < box_rightX < 180.0:
        error_msg = "Error 5: " + 'Watershed shapefile should be in WGS 84 coordinate system'
        validation_status = False

    if error_msg == "" or error_msg.startswith("Error 2") or error_msg.startswith("Error 3"):
        validation_status = True

        # create a dictinary of inputs. This helps carry program forward, eliminating the need to parse inputs again
        inputs_dictionary = {"user_name": request.user.username,
                             "simulation_name": request.POST['simulation_name'],
                             "simulation_start_date": request.POST['simulation_start_date_picker'],
                             "simulation_end_date": request.POST['simulation_end_date_picker'],
                             "USGS_gage": int(request.POST['USGS_gage']),

                             "outlet_y": float(outlet_y),
                             "outlet_x": float(outlet_x),
                             "box_topY": float(box_topY),
                             "box_bottomY": float(box_bottomY),
                             "box_rightX": float(box_rightX),
                             "box_leftX": float(box_leftX),

                             "timeseries_source": request.POST['timeseries_source'],

                             "threshold": int(request.POST['threshold']),
                             "cell_size": float(request.POST['cell_size']),
                             "timestep": float(request.POST['timestep']),
                             "model_engine": request.POST['model_engine'],

                             }

    else:
        validation_status = False

    return validation_status, error_msg, inputs_dictionary, geojson_files


def generate_uuid_file_path(file_name=None, root_path=None):
    if root_path == None:
        root_path = os.path.join(os.path.dirname(__file__), 'workspaces', 'user_workspaces')
    from uuid import uuid4
    uuid_path = os.path.join(root_path, uuid4().hex)
    os.makedirs(uuid_path)
    file_path = uuid_path
    if file_name:
        file_path = os.path.join(uuid_path, file_name)
    return file_path


def write_to_model_input_table(inputs_dictionary, hs_resource_id=""):
    """
     :param inputs_dictionary:
    :param hs_resource_id_created:
    :return: table_id of (pk) of the run information added to the dictionary
    """

    user_name = inputs_dictionary['user_name']
    simulation_name = inputs_dictionary['simulation_name']
    simulation_start_date = inputs_dictionary['simulation_start_date']
    simulation_end_date = inputs_dictionary['simulation_end_date']
    USGS_gage = int(inputs_dictionary['USGS_gage'])

    outlet_x = float(inputs_dictionary['outlet_x'])
    outlet_y = float(inputs_dictionary['outlet_y'])
    box_topY = float(inputs_dictionary['box_topY'])
    box_bottomY = float(inputs_dictionary['box_bottomY'])
    box_rightX = float(inputs_dictionary['box_rightX'])
    box_leftX = float(inputs_dictionary['box_leftX'])

    timeseries_source = inputs_dictionary['timeseries_source']
    threshold = float(inputs_dictionary['threshold'])
    cell_size = float(inputs_dictionary['cell_size'])
    timestep = float(inputs_dictionary['timestep'])

    model_engine = inputs_dictionary['model_engine']

    # :TODO, take these values from from input_dictionary
    remarks = ''
    user_option = ''

    # other model parameter is string or text, combining parametes with __ (double underscore)
    other_model_parameters = str(timeseries_source) + "__" + str(threshold) + "__" + str(cell_size) + "__" + str(
        timestep)

    # :TODO write only when sim_name is different for a user
    from .model import SessionMaker, model_inputs_table  # , model_calibration_table, engine,Base
    session = SessionMaker()  # Make session

    # one etnry / row
    one_run = model_inputs_table(user_name=user_name, simulation_name=simulation_name, hs_resource_id=hs_resource_id,
                                 simulation_start_date=simulation_start_date, simulation_end_date=simulation_end_date,
                                 USGS_gage=USGS_gage,
                                 outlet_x=outlet_x, outlet_y=outlet_y, box_topY=box_topY, box_bottomY=box_bottomY,
                                 box_rightX=box_rightX, box_leftX=box_leftX,
                                 model_engine=model_engine, other_model_parameters=other_model_parameters,
                                 remarks=remarks, user_option=user_option)
    session.add(one_run)
    session.commit()
    print "Run details written successfully to model_input_table", one_run

    # read the id, whcih is equal to lenght of total item in the simulationlist for the user
    current_model_inputs_table_id = str(len(session.query(model_inputs_table).filter(
        model_inputs_table.user_name == user_name).all()))  # because PK is the same as no of rows, i.e. length

    return current_model_inputs_table_id


def write_to_model_calibration_table(hs_resource_id=None, model_input_table_id=None, numeric_parameters_list=None,
                                     calibration_parameters_list=None):
    '''
    list, which will be converted string separated by __ double underscore
    :param numeric_parameters_list:   [pvs_t0, vo_t0 , qc_t0, kc] for topkapi
    :param calib_parameters_list:     [fac_l, fac_ks, fac_n_o, fac_n_c, fac_th_s]
    :param model_input_table_id:      The foreign key
    :return:
    '''
    if numeric_parameters_list == None:
        numeric_parameters_list = [90.0, 100.0, 0, 1]
    if calibration_parameters_list == None:
        calibration_parameters_list = [1, 1, 1, 1, 1]

    # make the exam same list, but change numbers to string
    numeric_parameters_list = [str(item) for item in numeric_parameters_list]
    calibration_parameters_list = [str(item) for item in calibration_parameters_list]

    # Database accepts string, so combining parametes with __ (double underscore)
    numeric_parameters = '__'.join(numeric_parameters_list)
    calibration_parameters = '__'.join(calibration_parameters_list)

    # :TODO write only when sim_name is different for a user
    from .model import engine, Base, SessionMaker, model_calibration_table, model_inputs_table
    session = SessionMaker()  # Make session

    # calculate model_input_table_id
    if model_input_table_id is None and hs_resource_id != None:
        qry = session.query(model_inputs_table.id).filter(
            model_inputs_table.hs_resource_id == hs_resource_id).all()  # because PK is the same as no of rows, i.e. length
        model_input_table_id = qry[-1][0]

    # one etnry / row
    one_run = model_calibration_table(numeric_parameters=numeric_parameters,
                                      calibration_parameters=calibration_parameters,
                                      input_table_id=model_input_table_id)
    session.add(one_run)
    session.commit()
    print "Run details written successfully to model_calibration_table"

    # read the id
    # current_model_calibration_table_id = str(len(session.query(model_calibration_table).filter(
    #     model_calibration_table.input_table_id == model_input_table_id).all()))  # because PK is the same as no of rows, i.e. length

    all_row = session.query(model_calibration_table).filter(
        model_calibration_table.input_table_id == model_input_table_id).all()
    current_model_calibration_table_id = all_row[0].id  # this query will only give one row. For that row, give id

    return current_model_calibration_table_id


def write_to_model_result_table(model_calibration_table_id, timeseries_discharge_list):
    '''
    :param: model_calibration_table_id:     The foriegn ID to reference the model_calibration_table
    INVALID :param  timeseries_discharge_list:       [   [datetime.datetime(2015, 1, 1, 0, 0), 2.0, 3.1],  [datetime.datetime(2015, 1, 2, 0, 0),2.35, 3.5]   ]
    :param timeseries_discharge_list [(datetime.datetime(2015, 1, 1, 0, 0), 1, 5), (datetime.datetime(2015, 1, 1, 0, 0), 6,5), i.e. [(datetime, sim,obs), (datetime, sim,obs)...]
           timeseries_discharge_list [(datetime.datetime(2015, 1, 1, 0, 0), 1), (datetime.datetime(2015, 1, 1, 0, 0), 6),
    :return:
    '''
    from .model import SessionMaker, model_result_table
    session = SessionMaker()

    for one_tuple in timeseries_discharge_list:
        q_obs = one_tuple[2]
        if len(timeseries_discharge_list[0]) == 2:  # i.e. no observed flow
            q_obs = 0

        one_run = model_result_table(date_time=one_tuple[0], simulated_discharge=one_tuple[1], observed_discharge=q_obs,
                                     model_calibration_id=model_calibration_table_id)
        session.add(one_run)

    session.commit()
    print "Run details written successfully to model_results_table"
    return


def create_table_element(table_name, user_name):
    from .model import engine, Base, SessionMaker, model_calibration_table, model_inputs_table, model_result_table
    from tethys_sdk.gizmos import TableView
    from sqlalchemy import inspect
    import sqlalchemy
    session = SessionMaker()  # Make session

    # qry1 = session.query(model_inputs_table).filter(model_inputs_table.simulation_name == 'simulation-1').delete()  # because PK is the same as no of rows, i.e. length
    # print 'deleted or not, ', qry1
    # test_string = qry1
    # qry = session.query(model_inputs_table.simulation_name).filter(model_inputs_table.user_name == user_name).all()  # because PK is the same as no of rows, i.e. length
    # test_string = qry
    # print test_string
    # foo_col = sqlalchemy.sql.column('foo')
    # s = sqlalchemy.sql.select(['*']).where(foo_col == 1)

    model_input_rows = []
    model_input_cols = model_inputs_table.__table__.columns

    qry = session.query(model_inputs_table).filter(
        model_inputs_table.user_name == user_name).all()  # because PK is the same as no of rows, i.e. length
    test_string = model_input_cols
    for row in qry:
        row_tuple = (row.simulation_name, row.hs_resource_id,  # row.simulation_start_date, row.simulation_end_date,
                     row.USGS_gage, row.outlet_x, row.outlet_y,
                     # row.box_topY,row.box_bottomY,row.box_rightX, row.box_leftX,
                     row.model_engine,
                     row.other_model_parameters.split('__')[0], row.other_model_parameters.split('__')[1],
                     row.other_model_parameters.split('__')[2], row.other_model_parameters.split('__')[3],
                     # ,row.remarks ,row.user_option
                     )
        model_input_rows.append(row_tuple)

    table_query = TableView(column_names=model_input_cols,
                            rows=model_input_rows,
                            hover=True,
                            striped=True,
                            bordered=False,
                            condensed=True)


def rename_shapefile_collection(shapefile_dict, basename):
    import uuid, os, shutil
    extension = uuid.uuid4().hex
    shp_folder = os.path.split(shapefile_dict['shp'])[0]

    new_dir = os.path.join(shp_folder, extension + "_" + basename)
    os.mkdir(new_dir)

    for key, shp_fname in shapefile_dict.iteritems():
        new_fname = new_dir + '.' + key  # os.path.split(shp_fname)[0] + '/' +  extension +"_" +  basename + '.'+ key
        os.rename(shp_fname, new_fname)
        shutil.copy2(new_fname, new_dir)
        if os.path.exists(shp_fname):
            os.remove(shp_fname)
            os.remove(new_fname)

    shutil.make_archive(new_dir, 'zip', new_dir)
    print 'Shapefiles zipped at ', new_dir + '.zip'
    return new_dir + '.zip'


def create_tethysGizmos_from_json(json_data):
    # hs_resource_id_created = hs_resource_id_loaded = hs_resource_id  # json_data['hs_res_id_created']

    hydrograph_series_sim = json_data['hydrograph_series_sim']
    hydrograph_series_obs = json_data['hydrograph_series_obs']
    eta = json_data['eta']
    vo = json_data['vo']
    vc = json_data['vc']
    vs = json_data['vs']
    ppt = json_data['ppt']

    ppt_cum = json_data['ppt_cum']  # cumulative
    eta_cum = json_data['eta_cum']
    q_obs_cum = json_data['q_obs_cum']
    q_sim_cum = json_data['q_sim_cum']

    r2_value = json_data['r2_value']
    nash_value = json_data['nash_value']

    # init values in the form
    if json_data['calib_parameter'] != None:
        fac_L_init = json_data['calib_parameter']['fac_l']
        fac_Ks_init = json_data['calib_parameter']['fac_ks']
        fac_n_o_init = json_data['calib_parameter']['fac_n_o']
        fac_n_c_init = json_data['calib_parameter']['fac_n_c']
        fac_th_s_init = json_data['calib_parameter']['fac_th_s']
    if json_data['numeric_param'] != None:
        pvs_t0_init = json_data['numeric_param']['pvs_t0']
        vo_t0_init = json_data['numeric_param']['vo_t0']
        qc_t0_init = json_data['numeric_param']['qc_t0']
        kc_init = json_data['numeric_param']['kc']

    # configure tethys gizmos
    hydrograph_opacity = 0.1

    q_sim_obj = TimeSeries(
        height='300px', width='500px', engine='highcharts', title=' Simulated Hydrograph ',
        subtitle="Simulated and Observed flow  ",
        y_axis_title='Discharge', y_axis_units='cfs',
        series=[{
            'name': 'Simulated Flow',
            'data': hydrograph_series_sim
        }])

    q_obs_obj = TimeSeries(
        height='500px', width='500px', engine='highcharts', title='Observed (actual) Hydrograph ',
        subtitle="Simulated and Observed flow  ",
        y_axis_title='Discharge', y_axis_units='cfs',
        series=[{
            'name': 'Simulated Flow',
            'data': hydrograph_series_obs
        }])

    q_sim_obs_obj = TimeSeries(
        height='300px',
        width='500px',
        engine='highcharts',
        title="Simulated and Observed flow  ",
        subtitle='Nash value: %s, R2: %s' % (nash_value, r2_value),
        y_axis_title='Discharge',
        y_axis_units='cfs',
        series=[{
            'name': 'Simulated Hydrograph',
            'data': hydrograph_series_sim,
            'fillOpacity': hydrograph_opacity,
        }, {
            'name': 'Observed Hydrograph',
            'data': hydrograph_series_obs,
            'fillOpacity': hydrograph_opacity,
        }]
    )

    vol_bal_graphs = TimeSeries(
        height='600px',
        width='500px',
        engine='highcharts',
        title="Cumulative volume of water in the basin",
        y_axis_title='Volume of water ',
        y_axis_units='mm',
        series=[{
            'name': 'Simulated Q',
            'data': q_sim_cum,
            'fillOpacity': hydrograph_opacity,
        }, {
            'name': 'Observed Q',
            'data': q_obs_cum,
            'fillOpacity': hydrograph_opacity,
        }, {
            'name': 'ETa',
            'data': eta_cum,
            'fillOpacity': hydrograph_opacity,
        }, {
            'name': 'PPT',
            'data': ppt_cum,
            'fillOpacity': hydrograph_opacity,
        }
        ])

    vc_ts_obj_loaded = create_1d(timeseries_list=vc, label='Average Water Volume in Channel Cells',
                                 unit='mm/day')
    vs_ts_obj_loaded = create_1d(timeseries_list=vs, label='Average Water Volume in Soil Cells',
                                 unit='mm/day')
    vo_ts_obj_loaded = create_1d(timeseries_list=vo, label='Average Water Volume in Overland Cells',
                                 unit='mm/day')
    ppt_ts_obj_loaded = create_1d(timeseries_list=ppt, label='Rainfall', unit='mm/day')
    eta_ts_obj_loaded = create_1d(timeseries_list=eta, label='Actual Evapotranspiration', unit='mm/day')


def create_tethysTableView_simulationRecord(user_name):
    from tethys_sdk.gizmos import TableView
    from .model import engine, Base, SessionMaker, model_calibration_table, model_inputs_table
    from sqlalchemy import inspect
    import sqlalchemy
    session = SessionMaker()  # Make session

    # qry1 = session.query(model_inputs_table).filter(model_inputs_table.simulation_name == 'simulation-1').delete()  # because PK is the same as no of rows, i.e. length
    # print 'deleted or not, ', qry1
    # test_string = qry1

    # qry = session.query(model_inputs_table.simulation_name).filter(model_inputs_table.user_name == user_name).all()  # because PK is the same as no of rows, i.e. length
    # test_string = qry
    # print test_string
    # foo_col = sqlalchemy.sql.column('foo')
    # s = sqlalchemy.sql.select(['*']).where(foo_col == 1)

    model_input_rows = []
    model_input_cols = ('Simulation name', 'hs_res_id',  # 'start', 'end',
                        'usgs gage', 'outlet X', 'outlet Y',
                        'box_topY','box_bottomY','box_rightX','box_leftX',
                        # 'model_engine', 'rain/et source',  'timestep',
                        'stream threshold', 'Cell size',
                        # 'remarks', 'user_option'
                        )
    # model_input_cols = model_inputs_table.__table__.columns

    qry = session.query(model_inputs_table).filter(
        model_inputs_table.user_name == user_name).all()  # because PK is the same as no of rows, i.e. length
    test_string = model_input_cols  # .__getitem__()
    for row in qry:
        test_string = round(float(row.box_topY), 3)
        row_tuple = (row.simulation_name, row.hs_resource_id,  # row.simulation_start_date, row.simulation_end_date,
                     row.USGS_gage, row.outlet_x, row.outlet_y,
                     round(row.box_topY, 3),round(row.box_bottomY, 3),round(row.box_rightX, 3), round(row.box_leftX, 3),
                     # row.model_engine,
                     row.other_model_parameters.split('__')[0], row.other_model_parameters.split('__')[1],   #cell size
                     # row.other_model_parameters.split('__')[2], row.other_model_parameters.split('__')[3], #timestep
                     # ,row.remarks ,row.user_option
                     )
        model_input_rows.append(row_tuple)

    table_query = TableView(column_names=model_input_cols,
                            rows=model_input_rows,
                            hover=True,
                            striped=True,
                            bordered=False,
                            condensed=True)
    return table_query


def loadpytopkapi(hs_res_id, out_folder=""):
            # output_hs_rs_id_txt='pytopkpai_model_files_metadata.txt',output_q_sim_txt='output_q_sim_retreived.txt',  output_response_txt = 'output_response_json.txt'


    run_model_call = HDS.loadpytopkapi(hs_res_id= hs_res_id)


    if out_folder == "":
        out_folder  = generate_uuid_file_path()

    responseJSON = run_model_call['output_response_txt']
    temp_file = out_folder + '/' + os.path.basename(responseJSON)
    HDS.download_file(responseJSON, temp_file)

    print run_model_call

    return out_folder + '/' + os.path.basename(responseJSON)  # ,      out_folder + '/' + os.path.basename(hydrograph_txt_file)


def modifypytopkapi(hs_res_id, out_folder="",  fac_l=1.0, fac_ks=1.0, fac_n_o=1.0, fac_n_c=1.0,fac_th_s=1.0,
                    pvs_t0=80.0 ,vo_t0=0.0 ,qc_t0=0.0 ,kc=1.0 ): #, output_response_txt = 'output_response_json.txt'):

    run_model_call = HDS.modifypytopkapi(fac_l=fac_l, fac_ks=fac_ks, fac_n_o=fac_n_o, fac_n_c=fac_n_c,fac_th_s=fac_th_s,
                                         pvs_t0=pvs_t0 ,vo_t0 =vo_t0 ,qc_t0=qc_t0 ,kc = kc, hs_res_id=hs_res_id  )

    print 'run_model_call =', run_model_call


    if out_folder == "":
        out_folder  = generate_uuid_file_path()

    responseJSON = run_model_call['output_response_txt']
    temp_file = out_folder + '/' + os.path.basename(responseJSON)
    HDS.download_file(responseJSON, temp_file)

    print run_model_call

    return out_folder + '/' + os.path.basename(responseJSON)  # ,      out_folder + '/' + os.path.basename(hydrograph_txt_file)

def download_geospatial_and_forcing_files(inputs_dictionary, download_request=['terrain'], out_folder=''):
    download_choices = ",".join(download_request)
    out_folder = generate_uuid_file_path()
    inputs_dictionary_json_file = os.path.join( out_folder , 'inputs.txt')

    with open (inputs_dictionary_json_file, 'w') as f:
        json.dump(inputs_dictionary,f, indent=4)

    json_hydrods_link = HDS.upload_file(inputs_dictionary_json_file)

    download_request = HDS.downloadgeospatialandforcingfiles(inputs_dictionary_json=json_hydrods_link, download_request=download_choices)

    print 'Functions for donwloaing files completed = ', download_request

    temp_file = out_folder + '/' + os.path.basename(download_request['output_response_txt'])
    HDS.download_file(download_request['output_response_txt'], temp_file)

    print 'temporary json respnse files = ',temp_file
    print 'download_request = ', download_request

    with open( temp_file ) as f:
        json_res = json.load(f)

        download_request['output_json_string'] = json_res

    print 'download_request=',download_request

    return download_request

def download_geospatial_and_forcing_files2(inputs_dictionary, download_request='geospatial', out_folder=''):
    """
    :param inputs_dictionary:  Dictionary. Inputs from Tethys, or user requesting the service
    :return: Timeseries file- hydrograph, or list of input files if the user only wants input files
    """




    prepared_file = {}

    # if out_folder == "":
    #     out_folder  = generate_uuid_file_path()

    # :TODO epsgCode has to be one consistent CS
    epsgCode = 102003 # North America Albers Equal Area Conic
    valid_simulation_name = ''.join(e for e in inputs_dictionary['simulation_name'] if e.isalnum())

    # #download UEB
    # run_ueb_request = HDS.runueb( watershedName=valid_simulation_name,
    #                               leftX=inputs_dictionary['box_leftX'],
    #                               topY=inputs_dictionary['box_topY'],
    #                               rightX=inputs_dictionary['box_rightX'],
    #                               bottomY=inputs_dictionary['box_bottomY'],
    #                               lat_outlet=inputs_dictionary['outlet_y'], lon_outlet=inputs_dictionary['outlet_x'],
    #                               streamThreshold=inputs_dictionary['threshold'],
    #                               startDateTime=inputs_dictionary['simulation_start_date'],
    #                               endDateTime=inputs_dictionary['simulation_end_date'], cell_size=inputs_dictionary['cell_size'],
    #
    #        # hs_client_id=None, hs_client_secret=None, token=None,
    #        epsgCode=102003,  usic=0, wsic=0, tic=0, wcic=0, ts_last=0,
    #        res_keywords='ueb, pytopkapi, melt+snowmelt', output_rain_and_melt='SWIT.nc',
    #        save_as=None)
    # print 'run_ueb_request=',run_ueb_request


    #:todo check if input is shapefile, or TIFF file. If it is, need to execute a function that gives bbox in WGS84


    # Clip Static DEM (i.e. DEM that is in HydroDS) to the domain given & Project, and Resample it
    subsetDEM_request = {'output_raster':'http://129.123.9.159:20199/files/data/user_6/DEM84.tif'}
    subsetDEM_request = HDS.subset_raster2(input_raster='nedWesternUS.tif', left=inputs_dictionary['box_leftX'],
                                           top=inputs_dictionary['box_topY'], right=inputs_dictionary['box_rightX'],
                                           bottom=inputs_dictionary['box_bottomY'], output_raster= 'DEM84.tif', cell_size=int(inputs_dictionary['cell_size']))

    DEM_resample_request = HDS.project_resample_raster(input_raster_url_path=subsetDEM_request['output_raster'],cell_size_dx=int(inputs_dictionary['cell_size']), cell_size_dy=int(inputs_dictionary['cell_size']), epsg_code=epsgCode, output_raster='DEM84'+str( int(inputs_dictionary['box_bottomY']))+'.tif', resample='bilinear')
    prepared_file['dem'] = DEM_resample_request

    # Create outlet shapefile from the point value
    outlet_shapefile_result = HDS.create_outlet_shapefile(point_x=inputs_dictionary['outlet_x'], point_y=inputs_dictionary['outlet_y'],output_shape_file_name= 'Outlet.shp'); print 'unprojected shapefile', outlet_shapefile_result
    project_shapefile_result = HDS.project_shapefile(outlet_shapefile_result['output_shape_file_name'],'OutletProj.shp', epsg_code=epsgCode); print 'project_shapefile_result =', project_shapefile_result
    prepared_file['outlet_shapefile'] = project_shapefile_result

    # Get complete raster set
    watershed_files = HDS.delineatewatershedtogetcompleterasterset(input_raster_url_path= DEM_resample_request['output_raster'],
                           threshold=inputs_dictionary['threshold'], output_raster='mask.tif', output_outlet_shapefile='corrected_outlet.shp',
                           input_outlet_shapefile_url_path=project_shapefile_result['output_shape_file'], )
    prepared_file['watershed_files'] = watershed_files
    print "watershed_files =", watershed_files



    # # clip all the files to mask
    # clip_hds_file_dict(watershed_files,watershed_files['output_raster'] )

    slope_raster = HDS.create_raster_slope(input_raster_url_path=watershed_files['output_fill_raster'], output_raster= 'slope.tif'); print 'slope_raster =', slope_raster
    prepared_file['slope_degree'] = slope_raster
    # :TODO resample to watershed files

    # soil_data_mask = watershed_files['output_raster']
    # soil_files = HDS.downloadsoildataforpytopkapi(input_watershed_raster_url_path=  soil_data_mask); print  'soil_files =', soil_files #,     #'http://129.123.9.159:20199/files/data/user_6/watershed_mukey.tif',


    subset_NLCD_result = HDS.project_clip_raster(input_raster='nlcd2011CONUS.tif',ref_raster_url_path=watershed_files['output_raster'], output_raster='nlcdProj' + str(inputs_dictionary['cell_size']) + '.tif');  print 'subset_NLCD_result', subset_NLCD_result
    LUT_location = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'utils' ,'LUT_NLCD2n.csv')
    LUT_overland = HDS.upload_file(LUT_location);  reclassify_nlcd = HDS.reclassifyrasterwithlut(LUT=LUT_overland, input_raster=subset_NLCD_result['output_raster']);  print 'reclassify_nlcd =', reclassify_nlcd
    prepared_file['nlcd'] = subset_NLCD_result
    prepared_file['mannings_n_overland'] = reclassify_nlcd

    print download_request
    if download_request =='soil':
        print ' Downloading soil files now... '
        soil_data_mask = watershed_files['output_raster']
        soil_files = HDS.downloadsoildataforpytopkapi5(input_watershed_raster_url_path=soil_data_mask)
        prepared_file['soil_files'] = soil_files
        print  'soil_files =', soil_files  # ,     #'http://129.123.9.159:20199/files/data/user_6/watershed_mukey.tif',

    if download_request == 'forcing':
        print ' Downloading forcing files now... '
        # if inputs_dictionary['timeseries_source'].lower() == 'daymet':

        # # # #:TODO Create rain and ET for 1000m first, and then resample it for user desired cell size # # #
        ref_dem_nc = {u'output_netcdf': u'http://129.123.9.159:20199/files/data/user_6/watershed.nc'}
        subsetDEM = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/DEM84.tif'}
        DEM_1000m = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/DEM84_1000m.tif'}
        rain_et_1000m = {u'output_et_reference_fname': u'http://129.123.9.159:20199/files/data/user_6/output_et.nc',
                         u'output_rain_fname': u'http://129.123.9.159:20199/files/data/user_6/output_ppt.nc'}

        if True:
            # ref_dem_nc0 = HDS.raster_to_netcdf_and_rename_variable(
            #     input_raster_url_path=watershed_files['output_raster'],
            #     output_netcdf='watershed0.nc')
            # ref_dem_nc = HDS.netcdf_rename_variable(input_netcdf_url_path=ref_dem_nc0['output_netcdf'],
            #                                         output_netcdf='watershed.nc',
            #                                         input_variable_name='Band1', output_variable_name='watershed')
            # print 'ref_dem_nc=', ref_dem_nc
            #
            mask_1000m = HDS.project_resample_raster(input_raster_url_path=watershed_files['output_raster'],
                                                     cell_size_dx=1000, cell_size_dy=1000, epsg_code=epsgCode,
                                                     output_raster='DEM84_1000m.tif', resample='bilinear')

            DEM_1000m = HDS.project_resample_raster(input_raster_url_path=subsetDEM['output_raster'],
                                                    cell_size_dx=1000, cell_size_dy=1000, epsg_code=epsgCode,
                                                    output_raster='DEM84_1000m.tif', resample='bilinear')
            print 'DEM_1000m=', DEM_1000m

            rain_et_1000m = HDS.calculaterainETfromdaymet(input_raster=mask_1000m['output_raster'],
                                                          input_dem=DEM_1000m['output_raster'],
                                                          startDate=inputs_dictionary['simulation_start_date'],
                                                          endDate=inputs_dictionary['simulation_end_date'],
                                                          cell_size=10000,
                                                          output_et_reference_fname='output_et.nc',
                                                          output_rain_fname='output_ppt.nc', save_as=None)
            print 'rain_et_1000m=', rain_et_1000m

            watershed_temp = HDS.raster_to_netcdf(watershed_files['output_raster'],
                                                  output_netcdf='watershed_temp.nc')
            # In the netCDF file rename the generic variable "Band1" to "watershed"
            Watershed_NC = HDS.netcdf_rename_variable(input_netcdf_url_path=watershed_temp['output_netcdf'],
                                                      output_netcdf='watershed.nc', input_variable_name='Band1',
                                                      output_variable_name='watershed')

            # resample, reproject
            rain_et = {}
            print 'Trying resampling nc'
            rain_trial = HDS.project_subset_resample_netcdf(
                input_netcdf_url_path=rain_et_1000m['output_rain_fname'],
                ref_netcdf_url_path=Watershed_NC['output_netcdf'], variable_name='prcp',
                output_netcdf='output_ppt_trial.nc')
            print 'Success resampling nc'

            print 'rain_trial=', rain_trial

            et_trial = HDS.project_subset_resample_netcdf(
                input_netcdf_url_path=rain_et_1000m['output_et_reference_fname'],
                ref_netcdf_url_path=Watershed_NC['output_netcdf'], variable_name='ETr',
                output_netcdf='output_et_trial.nc')
            print 'et_trial=', et_trial

            rain_et['output_rain_fname'] = rain_trial['output_netcdf']
            rain_et['output_et_reference_fname'] = et_trial['output_netcdf']

            print 'rain_et at user desired res', rain_et
            # stop


        abstractclimatedata = HDS.abstractclimatedata(input_raster=watershed_files['output_raster'],
                                                      cell_size=inputs_dictionary['cell_size'],
                                                      startDate=inputs_dictionary['simulation_start_date'],
                                                      endDate=inputs_dictionary['simulation_end_date'],
                                                      )
        prepared_file['abstractclimatedata'] = abstractclimatedata
        print abstractclimatedata

    return   prepared_file

def run_topnet(inputs_dictionary):
    __author__ = 'shams', 'Prasanna'

    list_of_outfiles_dict = []
    output_files_url_list = []
    output_files_list = []

    error_returned = None

    workingDir = os.path.join( os.path.abspath(os.path.dirname(__file__)) ,  "utils/TOPNET")
    leftX, topY, rightX, bottomY =inputs_dictionary['box_leftX'], inputs_dictionary['box_topY'], inputs_dictionary['box_rightX'], inputs_dictionary['box_bottomY']
    epsgCode = 102003  ## albers conic projection
    dx, dy = int(inputs_dictionary['cell_size']), int(inputs_dictionary['cell_size'])  # Grid cell sizes (m) for reprojection
    # Set parameters for watershed delineation
    streamThreshold =  inputs_dictionary['threshold_topnet']   #int( inputs_dictionary['threshold'] / ((int(inputs_dictionary['cell_size']) )**2)   )   # :TODo (TOPNET) understnad and make changes to the streamflow. Rightnow, it is in km2, IDK if this can be converted to TOPNET relevant threshold
    pk_min_threshold =  inputs_dictionary['pk_min_threshold'] #500
    pk_max_threshold = inputs_dictionary['pk_max_threshold']  #5000
    pk_num_thershold = inputs_dictionary['pk_num_thershold'] #12
    watershedName = ''.join(e for e in inputs_dictionary['simulation_name'] if e.isalnum())

    lat_outlet = inputs_dictionary['outlet_y']
    lon_outlet = inputs_dictionary['outlet_x']
    #### model start and end dates
    start_year = int(inputs_dictionary['simulation_start_date'].replace('-','/')[-4:])
    end_year = int(inputs_dictionary['simulation_end_date'].replace('-','/')[-4:])

    usgs_gage_number =inputs_dictionary['USGS_gage']

    nlcd_raster_resource = 'nlcd2011CONUS.tif'
    # uploading look up table file
    """ Subset DEM and Delineate Watershed"""
    input_static_DEM = 'nedWesternUS.tif'
    input_static_Soil_mukey = 'soil_mukey_westernUS.tif'

    upload_lutkcfile = HDS.upload_file(os.path.join(workingDir, "lutkc.txt"))
    # upload topnet control and watermangement files
    upload_lutlcfile = HDS.upload_file(os.path.join(workingDir, "lutluc.txt"))

    # leftX, topY, rightX, bottomY = -111.822, 42.128, -111.438, 41.686
    # lat_outlet = 41.744
    # lon_outlet = -111.7836
    # watershedName = 'LoganRiver_demo'
    # dx, dy = 30, 30
    # #### model start and end dates
    # start_year = 2000
    # end_year = 2001
    # usgs_gage_number = '10109001'

    try:

        # # offline run
        subsetDEM_request = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetDEM84.tif'}
        WatershedDEM = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetProj30.tif'}
        outlet_shapefile_result = {
            u'output_shape_file_name': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutlet.zip'}
        project_shapefile_result = {
            u'output_shape_file': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutletProj.zip'}
        Watershed_prod = {u'output_streamnetfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetnet.zip',
                          u'output_pointoutletshapefile': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetmoveOutlet2.zip',
                          u'output_distancefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetdist.tif',
                          u'output_coordfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetcoord.txt',
                          u'output_slopareafile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetslparr.tif',
                          u'output_watershedfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnet30WS.tif',
                          u'output_treefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnettree.txt'}
        download_process_climatedata = {
            u'output_temperaturefile': u'http://129.123.9.159:20199/files/data/user_6/tmaxtmintdew.dat',
            u'output_rainfile': u'http://129.123.9.159:20199/files/data/user_6/rain.dat',
            u'output_gagefile': u'http://129.123.9.159:20199/files/data/user_6/Climate_Gage.zip',
            u'output_cliparfile': u'http://129.123.9.159:20199/files/data/user_6/clipar.dat'}
        Create_Reach_Nodelink = {
            u'output_rchpropertiesfile': u'http://129.123.9.159:20199/files/data/user_6/rchproperties.txt',
            u'output_reachfile': u'http://129.123.9.159:20199/files/data/user_6/rchlink.txt',
            u'output_reachareafile': u'http://129.123.9.159:20199/files/data/user_6/rchareas.txt',
            u'output_nodefile': u'http://129.123.9.159:20199/files/data/user_6/nodelinks.txt'}
        Create_wet_distribution = {
            u'output_distributionfile': u'http://129.123.9.159:20199/files/data/user_6/distribution.txt'}
        subset_NLCD_result = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/lulcmmef.tif'}
        soil_data = {u'output_dth2_file': u'http://129.123.9.159:20199/files/data/user_6/dth2.tif',
                     u'output_f_file': u'http://129.123.9.159:20199/files/data/user_6/f.tif',
                     u'output_psif_file': u'http://129.123.9.159:20199/files/data/user_6/psif.tif',
                     u'output_sd_file': u'http://129.123.9.159:20199/files/data/user_6/sd.tif',
                     u'output_k_file': u'http://129.123.9.159:20199/files/data/user_6/ko.tif',
                     u'output_tran_file': u'http://129.123.9.159:20199/files/data/user_6/trans.tif',
                     u'output_dth1_file': u'http://129.123.9.159:20199/files/data/user_6/dth1.tif'}
        paramlisfile = {u'output_parspcfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetparam.txt'}
        ubsetDEM_request = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetDEM84.tif'}
        WatershedDEM = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetProj30.tif'}
        outlet_shapefile_result = {
            u'output_shape_file_name': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutlet.zip'}
        project_shapefile_result = {
            u'output_shape_file': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutletProj.zip'}
        Watershed_prod = {u'output_streamnetfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetnet.zip',
                          u'output_pointoutletshapefile': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetmoveOutlet2.zip',
                          u'output_distancefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetdist.tif',
                          u'output_coordfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetcoord.txt',
                          u'output_slopareafile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetslparr.tif',
                          u'output_watershedfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnet30WS.tif',
                          u'output_treefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnettree.txt'}
        download_process_climatedata = {
            u'output_temperaturefile': u'http://129.123.9.159:20199/files/data/user_6/tmaxtmintdew.dat',
            u'output_rainfile': u'http://129.123.9.159:20199/files/data/user_6/rain.dat',
            u'output_gagefile': u'http://129.123.9.159:20199/files/data/user_6/Climate_Gage.zip',
            u'output_cliparfile': u'http://129.123.9.159:20199/files/data/user_6/clipar.dat'}
        Create_Reach_Nodelink = {
            u'output_rchpropertiesfile': u'http://129.123.9.159:20199/files/data/user_6/rchproperties.txt',
            u'output_reachfile': u'http://129.123.9.159:20199/files/data/user_6/rchlink.txt',
            u'output_reachareafile': u'http://129.123.9.159:20199/files/data/user_6/rchareas.txt',
            u'output_nodefile': u'http://129.123.9.159:20199/files/data/user_6/nodelinks.txt'}
        Create_wet_distribution = {
            u'output_distributionfile': u'http://129.123.9.159:20199/files/data/user_6/distribution.txt'}
        subset_NLCD_result = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/lulcmmef.tif'}
        soil_data = {u'output_dth2_file': u'http://129.123.9.159:20199/files/data/user_6/dth2.tif',
                     u'output_f_file': u'http://129.123.9.159:20199/files/data/user_6/f.tif',
                     u'output_psif_file': u'http://129.123.9.159:20199/files/data/user_6/psif.tif',
                     u'output_sd_file': u'http://129.123.9.159:20199/files/data/user_6/sd.tif',
                     u'output_k_file': u'http://129.123.9.159:20199/files/data/user_6/ko.tif',
                     u'output_tran_file': u'http://129.123.9.159:20199/files/data/user_6/trans.tif',
                     u'output_dth1_file': u'http://129.123.9.159:20199/files/data/user_6/dth1.tif'}
        paramlisfile = {u'output_parspcfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetparam.txt'}
        ubsetDEM_request = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetDEM84.tif'}
        WatershedDEM = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetProj30.tif'}
        outlet_shapefile_result = {
            u'output_shape_file_name': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutlet.zip'}
        project_shapefile_result = {
            u'output_shape_file': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetOutletProj.zip'}
        Watershed_prod = {u'output_streamnetfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetnet.zip',
                          u'output_pointoutletshapefile': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetmoveOutlet2.zip',
                          u'output_distancefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetdist.tif',
                          u'output_coordfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetcoord.txt',
                          u'output_slopareafile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetslparr.tif',
                          u'output_watershedfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnet30WS.tif',
                          u'output_treefile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnettree.txt'}
        download_process_climatedata = {
            u'output_temperaturefile': u'http://129.123.9.159:20199/files/data/user_6/tmaxtmintdew.dat',
            u'output_rainfile': u'http://129.123.9.159:20199/files/data/user_6/rain.dat',
            u'output_gagefile': u'http://129.123.9.159:20199/files/data/user_6/Climate_Gage.zip',
            u'output_cliparfile': u'http://129.123.9.159:20199/files/data/user_6/clipar.dat'}
        Create_Reach_Nodelink = {
            u'output_rchpropertiesfile': u'http://129.123.9.159:20199/files/data/user_6/rchproperties.txt',
            u'output_reachfile': u'http://129.123.9.159:20199/files/data/user_6/rchlink.txt',
            u'output_reachareafile': u'http://129.123.9.159:20199/files/data/user_6/rchareas.txt',
            u'output_nodefile': u'http://129.123.9.159:20199/files/data/user_6/nodelinks.txt'}
        Create_wet_distribution = {
            u'output_distributionfile': u'http://129.123.9.159:20199/files/data/user_6/distribution.txt'}
        subset_NLCD_result = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/lulcmmef.tif'}
        soil_data = {u'output_dth2_file': u'http://129.123.9.159:20199/files/data/user_6/dth2.tif',
                     u'output_f_file': u'http://129.123.9.159:20199/files/data/user_6/f.tif',
                     u'output_psif_file': u'http://129.123.9.159:20199/files/data/user_6/psif.tif',
                     u'output_sd_file': u'http://129.123.9.159:20199/files/data/user_6/sd.tif',
                     u'output_k_file': u'http://129.123.9.159:20199/files/data/user_6/ko.tif',
                     u'output_tran_file': u'http://129.123.9.159:20199/files/data/user_6/trans.tif',
                     u'output_dth1_file': u'http://129.123.9.159:20199/files/data/user_6/dth1.tif'}
        paramlisfile = {u'output_parspcfile': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetparam.txt'}
        basinparfile = {u'output_basinfile': u'http://129.123.9.159:20199/files/data/user_6/basinpars.txt'}
        subsetprismrainfall_request = { u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/Logantopnetprism84.tif'}
        WatershedPRISMRainfall = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/LogantopnetProjPRISM30.tif'}

        project_climate_shapefile_result = {
            u'output_shape_file': u'http://129.123.9.159:20199/files/data/user_6/ClimateGageProj.zip'}
        create_rainweightfile = {
            u'output_rainweightfile': u'http://129.123.9.159:20199/files/data/user_6/rainweights.txt'}
        creat_latlonxyfile = {
            u'output_latlonfromxyfile': u'http://129.123.9.159:20199/files/data/user_6/latlongfromxy.txt'}

        subsetDEM_request = HDS.subset_raster(input_raster=input_static_DEM, left=leftX, top=topY, right=rightX,
                                              bottom=bottomY,output_raster=watershedName + 'DEM84.tif')
        print "subsetDEM_request = ", subsetDEM_request
        list_of_outfiles_dict.append(subsetDEM_request)

        myWatershedDEM = watershedName + 'Proj' + str(dx) + '.tif'
        WatershedDEM = HDS.project_resample_raster(input_raster_url_path=subsetDEM_request['output_raster'],
                                                              cell_size_dx=dx, cell_size_dy=dy, epsg_code=epsgCode,
                                                               output_raster=myWatershedDEM,resample='bilinear')
        print "WatershedDEM = ", WatershedDEM
        list_of_outfiles_dict.append(WatershedDEM)
        # subsetSoil_request = HDS.subset_raster(input_raster=input_static_Soil_mukey, left=leftX, top=topY, right=rightX,
        #                                       bottom=bottomY,output_raster=watershedName + 'Soil84.tif')
        # myWatershedSoil= watershedName + 'ProjSoil' + str(dx) + '.tif'
        # WatershedSoil = HDS.project_resample_raster(input_raster_url_path=subsetSoil_request['output_raster'],
        #                                                       cell_size_dx=dx, cell_size_dy=dy, epsg_code=epsgCode,
        #                                                        output_raster=myWatershedSoil,resample='bilinear')


        outlet_shapefile_result = HDS.create_outlet_shapefile(point_x=lon_outlet, point_y=lat_outlet,
                                                              output_shape_file_name=watershedName+'Outlet.shp')
        print "outlet_shapefile_result = ", outlet_shapefile_result
        list_of_outfiles_dict.append(outlet_shapefile_result)

        project_shapefile_result = HDS.project_shapefile(outlet_shapefile_result['output_shape_file_name'],
                                                         watershedName + 'OutletProj.shp',
                                                         epsg_code=epsgCode)
        print "project_shapefile_result = ", project_shapefile_result
        list_of_outfiles_dict.append(project_shapefile_result)

        Watershed_prod = HDS.delineate_watershed_peuker_douglas(input_raster_url_path=WatershedDEM['output_raster'],
                                        threshold=streamThreshold,peuker_min_threshold=pk_min_threshold,
                                        peuker_max_threshold=pk_max_threshold,peuker_number_threshold=pk_num_thershold,
                                        input_outlet_shapefile_url_path=project_shapefile_result['output_shape_file'],
                                        output_watershed_raster=watershedName + str(dx) +'WS.tif',
                                        output_outlet_shapefile=watershedName + 'moveOutlet2.shp',
                                        output_streamnetfile=watershedName+'net.shp',
                                        output_treefile=watershedName+'tree.txt',
                                        output_coordfile=watershedName+'coord.txt',
                                        output_slopearea_raster=watershedName+'slparr.tif',
                                        output_distance_raster=watershedName+'dist.tif')
        print "Watershed_prod = ", Watershed_prod
        list_of_outfiles_dict.append(Watershed_prod)

        """getting and processed climate data"""
        download_process_climatedata=HDS.get_daymet_data(input_raster_url_path=Watershed_prod['output_watershedfile'],
                                            start_year=start_year,
                                            end_year=end_year,
                                            output_gagefile='Climate_Gage.shp',
                                             output_rainfile='rain.dat',
                                             output_temperaturefile='tmaxtmintdew.dat',
                                             output_cliparfile='clipar.dat')

        print "download_process_climatedata = ", download_process_climatedata
        list_of_outfiles_dict.append(download_process_climatedata)


        """create nodelink and reachlink information"""
        Create_Reach_Nodelink=HDS.reachlink(input_DEM_raster_url_path=WatershedDEM['output_raster'],input_watershed_raster_url_path=Watershed_prod['output_watershedfile']
                                            ,input_treefile=Watershed_prod['output_treefile'],input_coordfile=Watershed_prod['output_coordfile'],
                                            output_reachfile='rchlink.txt',output_nodefile='nodelinks.txt',output_reachareafile='rchareas.txt',output_rchpropertiesfile='rchproperties.txt')
        print "Create_Reach_Nodelink = ", Create_Reach_Nodelink
        list_of_outfiles_dict.append(Create_Reach_Nodelink)

        ##get distribution
        Create_wet_distribution=HDS.distance_wetness_distribution(input_watershed_raster_url_path=Watershed_prod['output_watershedfile'],
                                           input_sloparearatio_raster_url_path=Watershed_prod['output_slopareafile'],input_distancnetostream_raster_url_path=Watershed_prod['output_distancefile'],
                                           output_distributionfile='distribution.txt')
        print "Create_wet_distribution = ", Create_wet_distribution
        list_of_outfiles_dict.append(Create_wet_distribution)

        ##getting landcover data

        subset_NLCD_result = HDS.project_clip_raster(input_raster=nlcd_raster_resource,ref_raster_url_path=Watershed_prod['output_watershedfile'],output_raster='lulcmmef.tif')
        print "subset_NLCD_result = ", subset_NLCD_result
        list_of_outfiles_dict.append(subset_NLCD_result)

        ##mukey_raster_resource='soil_mukey_westernUS.tif'
        ##soil_raster='http://hydrods-dev.uwrl.usu.edu:20199/files/data/user_5/watershed_mukey.tif'
        #http://hydrods-dev.uwrl.usu.edu:20199/api/dataservice/projectandcliprastertoreference?input_raster=soil_mukey_westernUS.tif&reference_raster=http://hydrods-dev.uwrl.usu.edu:20199/files/data/user_5/LoganRiver30WS.tif&output_raster=nlncd_spwan_proj_clip.tif

        #subset_soil_data= HDS.project_clip_raster(input_raster=mukey_raster_resource,ref_raster_url_path=ref_raster_url_path,output_raster='watershed_mukey.tif')
        #
        ##soil_raster=HDS.subset_raster_to_reference(WatershedSoil['output_raster'], Watershed_prod['output_watershedfile'],'Soil_Mukey_all.tif', save_as=None)

        soil_data=HDS.get_soil_data(input_watershed_raster_url_path=Watershed_prod['output_watershedfile'],output_f_raster='f.tif',output_k_raster='ko.tif',output_dth1_raster='dth1.tif'
                                 ,output_dth2_raster='dth2.tif',output_psif_raster='psif.tif',output_sd_raster='sd.tif',output_tran_raster='trans.tif')
        print "soil_data = ", soil_data
        list_of_outfiles_dict.append(soil_data)

        #create parameterspecificationfile

         #http://hydrods-dev.uwrl.usu.edu:20199/api/dataservice/downloadsoildata?Watershed_Raster=http://hydrods-dev.uwrl.usu.edu:20199/files/data/user_5/LoganRiver30WS.tif&
                            #  &output_f_file=f.tif&output_k_file=ko.tif&output_dth1_file=dth1.tif
                                #  &output_dth2_file=dth2.tif&output_psif_file=psif.tif&output_sd_file=sd.tif&output_tran_file=trans.tif
        #create parameterspecificationfile






        paramlisfile=HDS.createparameterlistfile(input_watershed_raster_url_path=WatershedDEM['output_raster'],output_file=watershedName+'param.txt')
        print "paramlisfile = ", paramlisfile
        list_of_outfiles_dict.append(paramlisfile)

        ##creating basinparameter file
        basinparfile=HDS.create_basinparamterfile(input_DEM_raster_url_path=WatershedDEM['output_raster'],input_watershed_raster_url_path=Watershed_prod['output_watershedfile'],
                                                  input_f_url_path=soil_data['output_f_file'],input_dth1_url_path=soil_data['output_dth1_file'],
                                                  input_dth2_url_path=soil_data['output_dth2_file'],input_k_url_path=soil_data['output_k_file'],
                                                  input_sd_url_path=soil_data['output_sd_file'],input_psif_url_path=soil_data['output_psif_file'],
                                                  input_tran_url_path=soil_data['output_tran_file'],
                                                  input_lulc_url_path=subset_NLCD_result['output_raster'],input_lutlc_url_path=upload_lutlcfile,
                                                  input_lutkc_url_path=upload_lutkcfile,input_parameterspecfile_url_path=paramlisfile['output_parspcfile'],
                                                  input_nodelinksfile_url_path=Create_Reach_Nodelink['output_nodefile'], output_basinparameterfile='basinpars.txt')
        print "basinparfile = ", basinparfile
        list_of_outfiles_dict.append(basinparfile)
        

        # # create rainweight file
        # Subset DEM and Delineate Watershed

        input_static_prismrainfall  = 'PRISM_ppt_30yr_normal_800mM2_annual_bil.bil'
        # input_static_prismrainfall  = '/home/ahmet/hydosdata/PRISM_annual/PRISM_ppt_30yr_normal_800mM2_annual_bil.bil'

        subsetprismrainfall_request = HDS.subset_raster(input_raster=input_static_prismrainfall , left=leftX-0.05, top=topY+0.05, right=rightX+0.05,
                                              bottom=bottomY-0.05,output_raster=watershedName + 'prism84.tif')
        print "subsetprismrainfall_request= ", subsetprismrainfall_request
        list_of_outfiles_dict.append(subsetprismrainfall_request)


        ## notes problem no such function susetrastertobbox is supported
        myWatershedPRISM= watershedName + 'ProjPRISM' + str(dx) + '.tif'


        ## notes problem no such function susetrastertobbox is supported
        myWatershedPRISM= watershedName + 'ProjPRISM' + str(dx) + '.tif'
        WatershedPRISMRainfall= HDS.project_resample_raster(input_raster_url_path=subsetprismrainfall_request['output_raster'],
                                                              cell_size_dx=dx, cell_size_dy=dy, epsg_code=epsgCode,
                                                              output_raster=myWatershedPRISM,resample='bilinear')
        print "WatershedPRISMRainfall = ", WatershedPRISMRainfall
        list_of_outfiles_dict.append(WatershedPRISMRainfall)



        project_climate_shapefile_result = HDS.project_shapefile(download_process_climatedata['output_gagefile'], 'ClimateGageProj.shp',
                                                         epsg_code=epsgCode)
        print "project_climate_shapefile_result = ", project_climate_shapefile_result
        list_of_outfiles_dict.append(project_climate_shapefile_result)


        create_rainweightfile=HDS.create_rainweight(input_watershed_raster_url_path=Watershed_prod['output_watershedfile'],
                                                    input_raingauge_shapefile_url_path=project_climate_shapefile_result['output_shape_file'],
                                                input_annual_rainfile=WatershedPRISMRainfall['output_raster'],
                                                    input_nodelink_file=Create_Reach_Nodelink['output_nodefile'],
                                                    output_rainweightfile='rainweights.txt')
        print "create_rainweightfile = ", create_rainweightfile
        list_of_outfiles_dict.append(create_rainweightfile)

        ##create latlonfromxy file
        creat_latlonxyfile=HDS.createlatlonfromxy(input_watershed_raster_url_path=Watershed_prod['output_watershedfile'],output_file='latlongfromxy.txt')
        print "creat_latlonxyfile = ", creat_latlonxyfile
        list_of_outfiles_dict.append(creat_latlonxyfile)


        # #get streamflow file :TODO, there seem to be some error with the function used in R
        # streamflow = HDS.download_streamflow(usgs_gage=usgs_gage_number, start_year=start_year, end_year=end_year,
        #                                      output_streamflow='streamflow_calibration.dat')
        # print "streamflow = ", streamflow
        # list_of_outfiles_dict.append(streamflow)



    except Exception, error_returned:
        print 'Failure to complete TOPNET input-file preparation!'

        file = open("error_auto.html", 'w')
        file.write(str(error_returned))

        file.close()
        print 'list_of_outfiles_dict=',list_of_outfiles_dict


    output_files_url_list = [u'http://129.123.9.159:20199/files/data/user_6/topnetdemoDEM84.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoProj30.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoOutlet.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoOutletProj.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemonet.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemomoveOutlet2.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemodist.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemocoord.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoslparr.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemo30WS.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemotree.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/tmaxtmintdew.dat',
                             u'http://129.123.9.159:20199/files/data/user_6/rain.dat',
                             u'http://129.123.9.159:20199/files/data/user_6/Climate_Gage.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/clipar.dat',
                             u'http://129.123.9.159:20199/files/data/user_6/rchproperties.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/rchlink.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/rchareas.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/nodelinks.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/distribution.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/lulcmmef.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/psif.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/f.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/dth2.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/sd.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/ko.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/trans.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/dth1.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoparam.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/basinpars.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoprism84.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/topnetdemoProjPRISM30.tif',
                             u'http://129.123.9.159:20199/files/data/user_6/ClimateGageProj.zip',
                             u'http://129.123.9.159:20199/files/data/user_6/rainweights.txt',
                             u'http://129.123.9.159:20199/files/data/user_6/latlongfromxy.txt']




    # get the list of URLs of the files created
    for a_dict in list_of_outfiles_dict:
        files = a_dict.values()
        for a_file in files:
            output_files_url_list.append(a_file)
            output_files_list.append(a_file.split('/')[-1])

    print 'output_files_url_list = ', output_files_url_list



    # download all the files
    working_folder = generate_uuid_file_path()
    out_folder = working_folder+ '/topnet-files'
    os.makedirs(out_folder)
    for file in output_files_url_list:
        temp_file = out_folder + '/' + os.path.basename(file)
        try:
            HDS.download_file(file, temp_file)
        except:
            pass


    # # zip the folder
    zipf = zipfile.ZipFile(working_folder+'/topnet-files.zip', 'w', zipfile.ZIP_DEFLATED)
    zipdir(working_folder, zipf)
    zipf.close()

    print ('Progress --> Zipping complete')  # working_dir

    # push to HydroDS for the link
    zipped_topnet_url = HDS.upload_file(working_folder+'/topnet-files.zip')
    print 'zipped_topnet_url =',zipped_topnet_url

    # push to HydroShare
    hs_res_id_created = push_topnet_to_hydroshare(simulation_name=inputs_dictionary['simulation_name'],
                              data_folder=out_folder,
                              hs_usr_name=None, hs_password=None,
                              hs_client_id=None, hs_client_secret=None, token=None)

    # delete the folder
    shutil.rmtree(working_folder)

    output_dict = {}
    output_dict['download_link']= zipped_topnet_url
    output_dict['output_files_url_list'] = output_files_url_list
    # output_dict['output_files_list'] = output_files_list
    output_dict['hs_res_id_created'] = hs_res_id_created

    return output_dict # { 'output_files_url':output_files_url_list  }

def call_runpytopkapi(inputs_dictionary, out_folder=''):
    """
    :param inputs_dictionary:  Dictionary. Inputs from Tethys, or user requesting the service
    :return: Timeseries file- hydrograph, or list of input files if the user only wants input files
    """

    valid_simulation_name = ''.join(e for e in inputs_dictionary['simulation_name'] if e.isalnum())
    epsgCode = 102003 # North America Albers Equal Area Conic

    subsetDEM_request = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/DEM84.tif'}
    subsetDEM_request = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/BlancoRiver.tif'}
    unprojected_shapefile = {u'output_shape_file_name': u'http://129.123.9.159:20199/files/data/user_6/Outlet.zip'}
    project_shapefile_result = {u'output_shape_file': u'http://129.123.9.159:20199/files/data/user_6/OutletProj.zip'}
    watershed_files = {u'output_contributing_area_raster': u'http://129.123.9.159:20199/files/data/user_6/ad8.tif',
                       u'output_outlet_shapefile': u'http://129.123.9.159:20199/files/data/user_6/corrected_outlet.zip',
                       u'output_stream_raster': u'http://129.123.9.159:20199/files/data/user_6/src.tif',
                       u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/mask.tif',
                       u'output_fill_raster': u'http://129.123.9.159:20199/files/data/user_6/fel.tif',
                       u'output_slope_raster': u'http://129.123.9.159:20199/files/data/user_6/sd8.tif',
                       u'output_flow_direction_raster': u'http://129.123.9.159:20199/files/data/user_6/p.tif'}
    slope_raster = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/slope.tif'}
    soil_files = {u'output_dth2_file': u'http://129.123.9.159:20199/files/data/user_6/dth2.tif',
                  u'output_dth1_file': u'http://129.123.9.159:20199/files/data/user_6/dth1.tif',
                  u'output_hydrogrp_file': u'http://129.123.9.159:20199/files/data/user_6/hydrogrp.tif',
                  u'output_psif_file': u'http://129.123.9.159:20199/files/data/user_6/psif.tif',
                  u'output_ksat_ssurgo_min_file': u'http://129.123.9.159:20199/files/data/user_6/ksat_ssurgo_min.tif',
                  u'output_ksat_LUT_file': u'http://129.123.9.159:20199/files/data/user_6/ksat_LUT.tif',
                  u'output_residual_soil_moisture_file': u'http://129.123.9.159:20199/files/data/user_6/RSM.tif',
                  u'output_ksat_ssurgo_wtd_file': u'http://129.123.9.159:20199/files/data/user_6/ksat_ssurgo_wtd.tif',
                  u'output_saturated_soil_moisture_file': u'http://129.123.9.159:20199/files/data/user_6/SSM.tif',
                  u'output_pore_size_distribution_file': u'http://129.123.9.159:20199/files/data/user_6/PSD.tif',
                  u'output_sd_file': u'http://129.123.9.159:20199/files/data/user_6/sd.tif',
                  u'output_bubbling_pressure_file': u'http://129.123.9.159:20199/files/data/user_6/BBL.tif'}
    subset_NLCD_result = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/nlcdProj100.0.tif'}
    reclassify_nlcd = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/reclassified_raster.tif'}
    rain_et = {u'output_et_reference_fname': u'http://129.123.9.159:20199/files/data/user_6/output_et.nc',
               u'output_rain_fname': u'http://129.123.9.159:20199/files/data/user_6/output_ppt.nc'}



    # # Clip Static DEM (i.e. DEM that is in HydroDS) to the domain given & Project, and Resample it
    subsetDEM_request = HDS.subset_raster2(input_raster='nedWesternUS.tif', left=inputs_dictionary['box_leftX'],
                                           top=inputs_dictionary['box_topY'], right=inputs_dictionary['box_rightX'],
                                           bottom=inputs_dictionary['box_bottomY'], cell_size= float(inputs_dictionary['cell_size']),
                                           output_raster= 'DEM84.tif')
    DEM_resample_request = HDS.project_resample_raster(input_raster_url_path=subsetDEM_request['output_raster'],cell_size_dx=int(inputs_dictionary['cell_size']), cell_size_dy=int(inputs_dictionary['cell_size']), epsg_code=epsgCode, output_raster='DEM84'+str( int(inputs_dictionary['cell_size']))+'.tif', resample='bilinear')
    #DEM_resample_request = HDS.project_resample_raster(input_raster_url_path='http://129.123.9.159:20199/files/data/user_6/loganSample100m.tif',cell_size_dx=int(inputs_dictionary['cell_size']), cell_size_dy=int(inputs_dictionary['cell_size']), epsg_code=epsgCode, output_raster='DEM84'+str( int(inputs_dictionary['cell_size']))+'.tif', resample='bilinear')


    # Create outlet shapefile from the point value
    outlet_shapefile_result = HDS.create_outlet_shapefile(point_x=inputs_dictionary['outlet_x'], point_y=inputs_dictionary['outlet_y'],output_shape_file_name= 'Outlet.shp'); print 'unprojected shapefile=', outlet_shapefile_result
    project_shapefile_result = HDS.project_shapefile(outlet_shapefile_result['output_shape_file_name'],'OutletProj.shp', epsg_code=epsgCode); print 'project_shapefile_result =', project_shapefile_result

    # Get complete raster set
    watershed_files = HDS.delineatewatershedtogetcompleterasterset(input_raster_url_path= DEM_resample_request['output_raster'],
                           threshold=inputs_dictionary['threshold'], output_raster='mask.tif', output_outlet_shapefile='corrected_outlet.shp',
                           input_outlet_shapefile_url_path=project_shapefile_result['output_shape_file'], )

    print "watershed_files =", watershed_files

    # # clip all the files to mask
    # clip_hds_file_dict(watershed_files,watershed_files['output_raster'] )

    slope_raster = HDS.create_raster_slope(input_raster_url_path=watershed_files['output_fill_raster'], output_raster= 'slope.tif'); print 'slope_raster =', slope_raster



    soil_files = HDS.downloadsoildataforpytopkapi5(input_watershed_raster_url_path=  watershed_files['output_raster']); print  'soil_files =', soil_files #,     #'http://129.123.9.159:20199/files/data/user_6/watershed_mukey.tif',


    subset_NLCD_result = HDS.project_clip_raster(input_raster='nlcd2011CONUS.tif',ref_raster_url_path=watershed_files['output_raster'], output_raster='nlcdProj' + str(inputs_dictionary['cell_size']) + '.tif');  print 'subset_NLCD_result=', subset_NLCD_result
    LUT_location = os.path.join(os.path.dirname(os.path.realpath(__file__)),'utils' ,'LUT_NLCD2n.csv')
    LUT_overland = HDS.upload_file(LUT_location);  reclassify_nlcd = HDS.reclassifyrasterwithlut(LUT=LUT_overland, input_raster=subset_NLCD_result['output_raster']);  print 'reclassify_nlcd =', reclassify_nlcd


    if inputs_dictionary['timeseries_source'].lower() =='daymet':

        # # # #:TODO Create rain and ET for 1000m first, and then resample it for user desired cell size # # #
        ref_dem_nc = {u'output_netcdf': u'http://129.123.9.159:20199/files/data/user_6/watershed.nc'}
        subsetDEM = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/DEM84.tif'}
        DEM_1000m = {u'output_raster': u'http://129.123.9.159:20199/files/data/user_6/DEM84_1000m.tif'}
        rain_et_1000m = {u'output_et_reference_fname': u'http://129.123.9.159:20199/files/data/user_6/output_et.nc',
                         u'output_rain_fname': u'http://129.123.9.159:20199/files/data/user_6/output_ppt.nc'}

        if False:
            ref_dem_nc0 = HDS.raster_to_netcdf_and_rename_variable(input_raster_url_path=watershed_files['output_raster'],
                                                                  output_netcdf='watershed0.nc')
            ref_dem_nc = HDS.netcdf_rename_variable(input_netcdf_url_path=ref_dem_nc0['output_netcdf'],
                                                    output_netcdf='watershed.nc',
                                                    input_variable_name='Band1', output_variable_name='watershed')
            print 'ref_dem_nc=', ref_dem_nc


            mask_1000m = HDS.project_resample_raster(input_raster_url_path=watershed_files['output_raster'],
                                                    cell_size_dx=1000,cell_size_dy=1000, epsg_code=epsgCode,
                                                    output_raster='DEM84_1000m.tif', resample='bilinear')

            DEM_1000m = HDS.project_resample_raster(input_raster_url_path=subsetDEM['output_raster'],
                                                    cell_size_dx=1000,cell_size_dy=1000, epsg_code=epsgCode,
                                                    output_raster='DEM84_1000m.tif', resample='bilinear')
            print 'DEM_1000m=',DEM_1000m



            rain_et_1000m = HDS.calculaterainETfromdaymet(input_raster=mask_1000m['output_raster'], input_dem=DEM_1000m['output_raster'],
                                                    startDate=inputs_dictionary['simulation_start_date'],endDate=inputs_dictionary['simulation_end_date'], cell_size=10000,
                                                    output_et_reference_fname='output_et.nc', output_rain_fname='output_ppt.nc', save_as=None)
            print 'rain_et_1000m=', rain_et_1000m



            watershed_temp = HDS.raster_to_netcdf(watershed_files['output_raster'],
                                                  output_netcdf='watershed_temp.nc')
            # In the netCDF file rename the generic variable "Band1" to "watershed"
            Watershed_NC = HDS.netcdf_rename_variable(input_netcdf_url_path=watershed_temp['output_netcdf'],
                                                      output_netcdf='watershed.nc', input_variable_name='Band1',
                                                      output_variable_name='watershed')


            watershed_temp = HDS.raster_to_netcdf('http://129.123.9.159:20199/files/data/user_6/mask.tif',
                                                  output_netcdf='watershed_temp.nc')
            # In the netCDF file rename the generic variable "Band1" to "watershed"
            Watershed_NC = HDS.netcdf_rename_variable(input_netcdf_url_path=watershed_temp['output_netcdf'],
                                                      output_netcdf='watershed.nc', input_variable_name='Band1',
                                                      output_variable_name='watershed')

            rain_trial = HDS.project_subset_resample_netcdf(input_netcdf_url_path='http://129.123.9.159:20199/files/data/user_6/output_ppt.nc',
                                                               ref_netcdf_url_path=Watershed_NC['output_netcdf'], variable_name='prcp',
                                                                output_netcdf='output_ppt_trial.nc')

            print rain_trial

            # resample, reproject
            rain_et = {}
            print 'Trying resampling nc'
            rain_trial = HDS.project_subset_resample_netcdf(input_netcdf_url_path=rain_et_1000m['output_rain_fname'],
                                                               ref_netcdf_url_path=Watershed_NC['output_netcdf'], variable_name='prcp',
                                                                output_netcdf='output_ppt_trial.nc')
            print 'Success resampling nc'

            print 'rain_trial=', rain_trial

            et_trial = HDS.project_subset_resample_netcdf(input_netcdf_url_path=rain_et_1000m['output_et_reference_fname'],
                                                               ref_netcdf_url_path=Watershed_NC['output_netcdf'], variable_name='ETr',
                                                                output_netcdf='output_et_trial.nc')
            print 'et_trial=', et_trial


            rain_et['output_rain_fname'] = rain_trial['output_netcdf']
            rain_et['output_et_reference_fname'] = et_trial['output_netcdf']

            print 'rain_et at user desired res', rain_et
            # stop

        # # # The existing code that works! # #  #
        print 'Getting forcing dataset for ', watershed_files['output_raster']
        rain_et = HDS.calculaterainETfromdaymet(input_raster=watershed_files['output_raster'], input_dem=watershed_files['output_fill_raster'],
                                                startDate=inputs_dictionary['simulation_start_date'],endDate=inputs_dictionary['simulation_end_date'], cell_size=inputs_dictionary['cell_size'],
                                                output_et_reference_fname='output_et.nc', output_rain_fname='output_ppt.nc', save_as=None)


    if inputs_dictionary['timeseries_source'].lower() == 'ueb':
        rain_et = {}
        rain_et['output_rain_fname'] = 'http://129.123.9.159:20199/files/data/user_6/SWIT_Logan_300m_2010_11.nc' # 'http://129.123.9.159:20199/files/data/user_6/SWIT_Logan_1000m_2010_11_12.nc  '#'http://129.123.9.159:20199/files/data/user_6/SWIT_qJuSJhB.nc '# 'http://129.123.9.159:20199/files/data/user_6/SWIT.nc'
        rain_et['output_et_reference_fname'] = watershed_files['output_raster'] #:TODO, need to think what to do for ET if UEB
    print 'rain_et =', rain_et


    run_model_call = HDS.runpytopkapi6(user_name=inputs_dictionary['user_name'],
                                       simulation_name=valid_simulation_name, #inputs_dictionary['simulation_name'],
                                       simulation_start_date=inputs_dictionary['simulation_start_date'],
                                       simulation_end_date=inputs_dictionary['simulation_end_date'],
                                       USGS_gage=inputs_dictionary['USGS_gage'],
                                       threshold=inputs_dictionary['threshold'],

                                       # channel_manning_fname=watershed_files['output_mannings_n_stream_raster'],
                                       overland_manning_fname=reclassify_nlcd['output_raster'],

                                       hillslope_fname=watershed_files['output_slope_raster'],
                                       # slope_raster['output_raster'], because sd8 is tan of angle, whereas slope is in degree
                                       dem_fname=watershed_files['output_fill_raster'],
                                       channel_network_fname=watershed_files['output_stream_raster'],
                                       mask_fname=watershed_files['output_raster'],
                                       flowdir_fname=watershed_files['output_flow_direction_raster'],

                                       pore_size_dist_fname=soil_files['output_pore_size_distribution_file'],
                                       bubbling_pressure_fname=soil_files['output_bubbling_pressure_file'],
                                       resid_moisture_content_fname=soil_files['output_residual_soil_moisture_file'],
                                       sat_moisture_content_fname=soil_files['output_saturated_soil_moisture_file'],
                                       conductivity_fname= soil_files['output_ksat_LUT_file'], #soil_files['output_ksat_ssurgo_wtd_file'],  # only change is here, based on downloadsoildataforpytopkapi3 or 4
                                       # soil_files['output_ksat_rawls_file'],
                                       soil_depth_fname=  watershed_files['output_raster'],                                          # soil_files['output_sd_file'],

                                       timestep=inputs_dictionary['timestep'],
                                       output_response_txt="pytopkpai_response.txt",
                                       rain_fname= rain_et['output_rain_fname'],
                                       et_fname= rain_et['output_et_reference_fname'],
                                       timeseries_source = inputs_dictionary['timeseries_source']
                                       )

    if out_folder == "":
        out_folder  = generate_uuid_file_path()

    responseJSON = run_model_call['output_response_txt']
    temp_file = out_folder + '/' + os.path.basename(responseJSON)
    HDS.download_file(responseJSON, temp_file)

    print run_model_call

    return out_folder + '/' + os.path.basename(responseJSON)  # ,      out_folder + '/' + os.path.basename(hydrograph_txt_file)



if __name__ == '__main__':
    zipf = zipfile.ZipFile('Python.zip', 'w', zipfile.ZIP_DEFLATED)
    zipdir('tmp/', zipf)
    zipf.close()






# # UN-USED or INCOMPLETE functions
def call_subprocess(cmdString, debugString):
    cmdargs = shlex.split(cmdString)
    debFile = open('debug_file.txt', 'w')
    debFile.write('Starting %s \n' % debugString)
    retValue = subprocess.call(cmdargs,stdout=debFile)
    if (retValue==0):
        debFile.write('%s Successful\n' % debugString)
        debFile.close()
    else:
        debFile.write('There was error in %s\n' % debugString)
        debFile.close()
def change_point_to_WGS84(list_of_points, in_shp_file):

    """
    :param list_of_points: a python list of points to be transformed to WGS 1984
    :param in_shp_file: shapefile, to read its input projection
    :return: a list of transformed points

    Helper Source:
    http://zevross.com/blog/2014/06/09/no-esri-no-problem-manipulate-shapefiles-with-the-python-library-osgeo/
    http://geoinformaticstutorial.blogspot.com/2012/10/reprojecting-shapefile-with-gdalogr-and.html
    """

    driver = ogr.GetDriverByName('ESRI Shapefile')
    dataSource = driver.Open(in_shp_file, 0)  # 0 means read-only, 1 means writeable
    layer = dataSource.GetLayer()

    sourceprj = layer.GetSpatialRef()
    targetprj = osr.SpatialReference()
    targetprj.ImportFromEPSG(4326)
    transform = osr.CoordinateTransformation(sourceprj, targetprj)

    #
    # # convert the points to WGS 84
    # point = ogr.CreateGeometryFromWkt("POINT (%s %s)"%(outlet_x,outlet_y ) )
    # point.Transform(transform)
    #
    # outlet_x = point.ExportToWkt()[0]
    # outlet_y = point.ExportToWkt()[1]
    #
    # #
    # # return list_of_transferred_points
def handle_uploaded_file(f):
    with open('some/file/name.txt', 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
def load_shapefile_to_db(shapefile_base="/usr/lib/tethys/src/tethys_apps/tethysapp/my_first_app/workspaces/user_workspaces/usr1/outlet_boundary/Wshed_BlackSmithFork", db='Spatial_dataset_service1'):
    # https://github.com/tethysplatform/tethys/blob/master/docs/tethys_sdk/spatial_dataset_services.rst

    from tethys_sdk.services import get_spatial_dataset_engine

    # create connection to "spatial data service" engine
    dataset_engine = get_spatial_dataset_engine(name=db)

    # # TODO: check if this is deleted later
    # # Example method with debug option
    # dataset_engine.list_layers(debug=True)

    # Create a workspace named after our app
    dataset_engine.create_workspace(workspace_id='my_first_app', uri='my-first-app')

    # Path to shapefile base for foo.shp, side cars files (e.g.: .shx, .dbf) will be
    # gathered in addition to the .shp file.
    shapefile_base = shapefile_base

    # Notice the workspace in the store_id parameter
    result = dataset_engine.create_shapefile_resource(store_id='my_first_app:Wshed_BlackSmithFork', shapefile_base=shapefile_base)

    # Check if it was successful
    if not result['success']:
        return result['error']
        raise



    return result['result']
def write_input_parameters_to_db(user_name, simulation_name, input_parameters_string, calibration_parameter_string):
    # NOT USED

    # write the inputs to the database
    from .model import engine, SessionMaker, Base, model_inputs_table, model_calibration_table

    Base.metadata.create_all(engine)  # Create tables
    session = SessionMaker()  # Make session

    one_run = model_inputs_table(user_name, input_parameters_string, calibration_parameter_string)

    session.add(one_run)
    session.commit()

    # read the id
    current_model_inputs_table_id = str(len(session.query(model_inputs_table).filter(
        model_inputs_table.user_name == user_name).all()))  # because PK is the same as no of rows, i.e. length

    return current_model_inputs_table_id

def get_outlet_xy_from_shp(shp_file, simulation_folder='/usr/lib/tethys/src/tethys_apps/tethysapp/my_first_app/workspaces/user_workspaces/usr1/'):
    from shapely.geometry import shape
    # # convert the django_memory_file format to original shapefile
    # filename = "outlet.shp"  # received file name
    # file_obj = shp_file
    # with open(simulation_folder +'/' + filename, 'w') as destination:
    #     for chunk in file_obj.chunks():
    #         destination.write(chunk)
    # shp_file = simulation_folder +'/' + filename
    #
    # # convert the django_memory_file format to original shapefile
    # filename = "outlet.shx"  # received file name
    # file_obj = shx_file
    # with open(simulation_folder +'/' + filename, 'w') as destination:
    #     for chunk in file_obj.chunks():
    #         destination.write(chunk)
    # shx_file = simulation_folder +'/' + filename

    # use fiona to get the bounds
    c = fiona.open(shp_file)

    outlet_x = c.bounds[0]
    outlet_y = c.bounds[1]

    # # ----------- projection --------------------

    # driver = ogr.GetDriverByName('ESRI Shapefile')
    # dataSource = driver.Open(shp_file, 0)  # 0 means read-only, 1 means writeable
    # layer = dataSource.GetLayer()
    # sourceprj = layer.GetSpatialRef()
    # targetprj = osr.SpatialReference()
    # targetprj.ImportFromEPSG(4326)
    # transform = osr.CoordinateTransformation(sourceprj, targetprj)
    #
    # if sourceprj != None:
    #     point = ogr.CreateGeometryFromWkt("POINT (1120351.57 741921.42)")
    #     point.Transform(transform)
    #
    #     outlet_xg = point.ExportToWkt()[0]
    #     outlet_y = point.ExportToWkt()[1]

    # # To TEST only
    # source = osr.SpatialReference()
    # source.ImportFromEPSG(2927)
    #
    # target = osr.SpatialReference()
    # target.ImportFromEPSG(4326)
    #
    # transform = osr.CoordinateTransformation(source, target)
    #
    # point = ogr.CreateGeometryFromWkt("POINT (1120351.57 741921.42)")
    # point.Transform(transform)
    #
    # outlet_x = point # TODO: get the x and Y from this string point


    # # ----------- projection --------------------

    return outlet_x, outlet_y

def get_box_xyxy_from_shp(shp_file, simulation_folder='/usr/lib/tethys/src/tethys_apps/tethysapp/my_first_app/workspaces/user_workspaces/usr1/'):
    from shapely.geometry import shape

    # # convert the django_memory_file format to original shapefile
    # filename = "watershed.shp"  # received file name
    # file_obj = shp_file
    # with open(simulation_folder +'/' + filename, 'w') as destination:
    #     for chunk in file_obj.chunks():
    #         destination.write(chunk)
    # shp_file = simulation_folder +'/' + filename
    #
    # # convert the django_memory_file format to original shapefile
    # filename = "watershed.shx"  # received file name
    # file_obj = shx_file
    # with open(simulation_folder +'/' + filename, 'w') as destination:
    #     for chunk in file_obj.chunks():
    #         destination.write(chunk)
    # shx_file = simulation_folder +'/' + filename

    c = fiona.open(shp_file)

    # first record
    first_shape = c.next()

    # shape(first_shape['geometry']) -> shapely geometry

    box_topY = shape(first_shape['geometry']).bounds[3]
    box_bottomY = shape(first_shape['geometry']).bounds[1]
    box_rightX = shape(first_shape['geometry']).bounds[2]
    box_leftX = shape(first_shape['geometry']).bounds[0]

    return box_rightX, box_bottomY, box_leftX, box_topY


def get_box_from_tif(tif_fname, simulation_folder=None):
    #gdalwarp infile.tif outfile.tif -t_srs "+proj=longlat +ellps=WGS84"
    minx=  None
    miny = None
    maxx = None
    maxy = None
    try:
        from osgeo import gdal
        ds = gdal.Open(tif_fname)
        width = ds.RasterXSize
        height = ds.RasterYSize
        gt = ds.GetGeoTransform()
        minx = gt[0]
        miny = gt[3] + width * gt[4] + height * gt[5]
        maxx = gt[0] + width * gt[1] + height * gt[2]
        maxy = gt[3]
    except Exception, e:
        print 'error: Tiff files contents is not supported. Try another Tiff file', e

    return maxx, miny, minx, maxy


# # In test phase functions
def test_hds():

    path = os.path.dirname(os.path.realpath(__file__)) + "/hydrogate_python_client"
    sys.path.append(path)

    from hydrogate import HydroDS

    # Create HydroDS object passing user login account for HydroDS api server
    HDS = HydroDS(username='pdahal', password="pDahal2016")

    workingDir = '/home/prasanna/Documents/test'
    #
    # # Set parameters for watershed delineation
    # streamThreshold = 100;  pk_min_threshold = 1000;  pk_max_threshold = 10000;  pk_num_thershold = 12
    #
    # # model start and end dates
    # startDateTime = "2010/10/01 0"; endDateTime = "2011/06/01 0"
    # start_year = 2000; end_year = 2010


    # #upload DEM 30 m for C22 Watershed
    DEM_30M = workingDir + '/DEM_Prj_f.tif'
    upload_30m_DEM =HDS.upload_file(file_to_upload=DEM_30M)     # file is projected
    print "DEM raster uploaded. The location of the DEM is: ", upload_30m_DEM

    # upload shapefiles
    outlet = workingDir + '/Outlet_BlackSmithFork.zip'
    wshed = workingDir + '/Outlet_BlackSmithFork.zip'
    upload_outlet = HDS.upload_file(file_to_upload=outlet)   # file is projected
    upload_wshed = HDS.upload_file(file_to_upload=wshed)        # file is projected
    print "Shapefiles uploaded. The location of the outlet is: ", upload_outlet

    hs_obj = HydroshareResource(upload_30m_DEM)
    hs_obj.add(upload_outlet)
    hs_obj.add(upload_wshed)
class HydroshareResource(object):
    #from hs_restclient import HydroShare, HydroShareAuthBasic
    def __init__(self, fpath="", username = "prasanna_310",  password = "Hydrology12!@" ):
        self.username = "prasanna_310"
        self.password = "Hydrology12!@"

        from hs_restclient import HydroShare, HydroShareAuthBasic
        auth = HydroShareAuthBasic(username=username, password=password)
        self.hs = HydroShare(auth=auth)

        self.day = date.today().strftime('%m/%d/%Y')
        self.abstract = 'The files created from hydrologic modeling app'
        self.title = 'Model input files'
        self.keywords = ('hydrologic modeling', 'app', 'tethys', 'TOPKAPI', 'RHEHSSys')
        self.rtype = 'GenericResource'
        self.metadata = '[{"coverage":{"type":"period", "value":{"start":"%s", "end":"%s"}}}, {"creator":{"name":"%s"}}]'%(self.day,self.day,self.username)
        self.fpath = fpath

        self.first_resource_id = self.hs.createResource(self.rtype, self.title, resource_file=self.fpath, keywords=self.keywords, abstract=self.abstract,
                                        metadata=self.metadata)
        print "Resource created Resource ID is: ", self.first_resource_id


    def add(self,fpath):
        resource_id = self.hs.addResourceFile(self.first_resource_id, fpath)
        print "Resource added Resource ID is: ", self.first_resource_id
        return resource_id


if __name__ == "__main__":
    working_dir = '/home/prasanna/tethysdev/tethysapp-my_first_app/tethysapp/my_first_app/workspaces/user_workspaces/usr1/retreived'
    outlet_shp = '/home/prasanna/tethysdev/tethysapp-my_first_app/tethysapp/my_first_app/workspaces/user_workspaces/usr1/outlet_boundary/Outlet_BlackSmithFork.shp'
    wshed_shp = '/home/prasanna/tethysdev/tethysapp-my_first_app/tethysapp/my_first_app/workspaces/user_workspaces/usr1/outlet_boundary/Wshed_BlackSmithFork.shp'

    # print "Creating and Adding to hydroshare....."
    # hs_object = HydroshareResource(wshed_shp)
    # resID2 = hs_object.add(outlet_shp)
    #
    # print "Retreiving data from hydroshare......."
    # auth = HydroShareAuthBasic(username='prasanna_310', password='Hydrology12!@')
    # hs = HydroShare(auth=auth)
    # file_to_retreive = 'Wshed_BlackSmithFork.shp'
    # hs.getResourceFile(resID2, 'Wshed_BlackSmithFork.shp', destination=working_dir)




