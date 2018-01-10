from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from oauthlib.oauth2 import TokenExpiredError
from hs_restclient import HydroShare, HydroShareAuthOAuth2, HydroShareNotAuthorized, HydroShareNotFound

# from tethys_apps.sdk.gizmos import *
from tethys_sdk.gizmos import *

import sys, os, json
import app_utils
import numpy as np

from datetime import datetime


# instead of writing arbitrary error, it might be a good idea to use this dictionary in returning errors
# this dictionary should be in a different file
errors = {'invalid_date': 'Error 1001. Input type invalid',
          'invalid_outlet': 'Error xx. Timeseries source selected not yet ready',
          'invalid_domain': 'Error xx. Domain source selected not yet ready',
          'invalid_USGS_gage': 'Error xx. USGS gage selected not correct, or not data not available for it',
          }


@login_required()
def home(request):
    """
    Controller for the app home page.
    """
    context = {}

    return render(request, 'hydrotop/home.html', context)

# init_channel_flow, init_overland_vol, init_soil_percentsat
def model_input(request):
    user_name = request.user.username
    OAuthHS = get_OAuthHS(request)
    user_name = OAuthHS['user_name']

    # Define Gizmo Options
    # from .model import engine, SessionMaker, Base, model_inputs_table, model_calibration_table

    # Query DB for gage objects, all the entries by the user name
    # give the value for thsi variable = 0 if the program is starting for the first time
    simulation_names_list = app_utils.create_simulation_list_after_querying_db(given_user_name=user_name)

    # init_channel_flow, init_overland_vol, init_soil_percentsat
    # # intials
    watershed_name = 'Plunge'  # 'RBC' , 'Santa Cruz', 'Barrow Creeks', 'Plunge' , Logan
    initials = {

        'Logan': {'simulation_name': 'Logan_sample', 'USGS_gage': '10109000', 'cell_size': '30', 't0': '10-01-2010',
                  't': '10-30-2010', 'threshold': '25', 'del_t': '24', 'x': '-111.7836', 'y': '41.7436',
                  'ymax': '42.12', 'xmax': '-111.44', 'ymin': '41.68', 'xmin': '-111.83' ,
                  'init_soil_percentsat':'30' },

        'RBC': {'simulation_name': 'RBC_sample', 'USGS_gage': '10172200', 'cell_size': '100', 't0': '10-01-2010',
                't': '10-03-2011', 'threshold': '2', 'del_t': '24', 'x': '-111.80624', 'y': '40.77968',
                'ymax': '40.8327', 'xmax': '-111.728', 'ymin': '40.772', 'xmin': '-111.834',
                'init_soil_percentsat': '30'},

        'Plunge': {'simulation_name': 'Plunge_demo', 'USGS_gage': '11055500', 'cell_size': '100', 't0': '10-01-2010',
                   't': '10-01-2011', 'threshold': '5', 'del_t': '24', 'x': '-117.141284', 'y': '34.12128',
                   # 'ymax':'34.2336', 'xmax': '-117.048046', 'ymin': '34.10883', 'xmin': '-117.168289',
                   'ymax': '34.23', 'xmax': '-117.1', 'ymin': '34.10883', 'xmin': '-117.2',
                   'init_soil_percentsat': '30'
                   },

        'SantaCruz': {'simulation_name': 'SantaCruz_demo', 'USGS_gage': '11124500', 'cell_size': '500',
                      't0': '10-01-2010',
                      't': '10-01-2011', 'threshold': '5', 'del_t': '24', 'x': '-119.90873', 'y': '34.59637',
                      'ymax': '34.714', 'xmax': '-119.781', 'ymin': '34.586', 'xmin': '-119.925',
                      'init_soil_percentsat': '30'},


        'SanMarcos': {'simulation_name': 'SANMARCOS_TX_2010', 'USGS_gage': '11028500', 'cell_size': '100',
                       't0': '10-01-2010',
                       't': '10-01-2011', 'threshold': '15', 'del_t': '24', 'x': '-116.9455844', 'y': '33.0522655',
                       'ymax': '30.213', 'xmax': '-97.956', 'ymin': '30.027', 'xmin': '-97.99',
                       'init_soil_percentsat': '30'},

    }

    simulation_name = TextInput(display_text='Simulation name', name='simulation_name',
                                initial=initials[watershed_name]['simulation_name'])
    USGS_gage = TextInput(display_text='USGS gage nearby', name='USGS_gage',
                          initial=initials[watershed_name]['USGS_gage'])
    cell_size = TextInput(display_text='Cell size in meters', name='cell_size',
                          initial=initials[watershed_name]['cell_size'])
    timestep = TextInput(display_text='Timestep in hrs', name='timestep',
                         initial=initials[watershed_name]['del_t'])  # , append="hours"
    simulation_start_date_picker = DatePicker(name='simulation_start_date_picker', display_text='Start Date',
                                              autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                              # '01-01-2010'
                                              start_view='year', today_button=True,
                                              initial=initials[watershed_name]['t0'])
    simulation_end_date_picker = DatePicker(name='simulation_end_date_picker', display_text='End Date',
                                            autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                            # '01-01-2010'
                                            start_view='year', today_button=False,
                                            initial=initials[watershed_name]['t'])
    threshold = TextInput(display_text='Stream threshold in square km', name='threshold',
                          initial=initials[watershed_name]['threshold'])


    init_soil_percentsat = TextInput(display_text='Intial saturation in soil cells (in %) ', name='init_soil_percentsat',
                          initial=initials[watershed_name]['init_soil_percentsat'])
    init_overland_vol = TextInput(display_text='Intial volume of water in overland cells (in m3) ', name='init_overland_vol',
                          initial=str(  0.0003* float(initials[watershed_name]['cell_size'])**2  ))
    init_channel_flow = TextInput(display_text='Intial flow of water in channel cells (in m3/s) ', name='init_channel_flow',
                          initial=str( float(initials[watershed_name]['cell_size']) * .001) )

    threshold_topnet = TextInput(display_text='Stream threshold', name='threshold_topnet', initial=100)
    pk_min_threshold = TextInput(display_text='pk_min_threshold', name='pk_min_threshold', initial=500)
    pk_max_threshold = TextInput(display_text='pk_max_threshold', name='pk_max_threshold', initial=50000)
    pk_num_thershold = TextInput(display_text='pk_num_thershold', name='pk_num_thershold', initial=12)

    epsgCode = TextInput(display_text='EPSG projection for outputs', name='epsgCode', initial=102003)

    timeseries_source = SelectInput(display_text='Forcing source',
                                    name='timeseries_source',
                                    multiple=False,
                                    options=[('Daymet', 'Daymet'), ('UEB', 'UEB')],
                                    initial=['Daymet'],
                                    original=['Daymet'])


    model_engine = SelectInput(display_text='Choose an action',
                               name='model_engine',
                               multiple=False,
                               options=[('Download geospatial files', 'download'), ('Prepare TOPKAPI model', 'TOPKAPI'),
                                        ('Prepare TOPNET input-files', 'TOPNET')],
                               initial=['download'],
                               original=['download']
                               )

    # # html form to django form

    # (Any Watershed)
    outlet_x = TextInput(display_text='Longitude', name='outlet_x',
                         initial=initials[watershed_name]['x'])  # 41.74025, -111.7915
    outlet_y = TextInput(display_text='Latitude', name='outlet_y', initial=initials[watershed_name]['y'])

    box_topY = TextInput(display_text='North Y', name='box_topY', initial=initials[watershed_name]['ymax'])
    box_rightX = TextInput(display_text='East X', name='box_rightX', initial=initials[watershed_name]['xmax'])
    box_bottomY = TextInput(display_text='South Y', name='box_bottomY', initial=initials[watershed_name]['ymin'])
    box_leftX = TextInput(display_text='West X', name='box_leftX', initial=initials[watershed_name]['xmin'])

    outlet_hs = TextInput(display_text='', name='outlet_hs', initial='')
    bounding_box_hs = TextInput(display_text='', name='bounding_box_hs', initial='')

    existing_sim_res_id = TextInput(display_text='', name='existing_sim_res_id', initial='')

    form_error = ""
    test_function_response = ""
    geojson_files = {}
    geojson_outlet = 'Default'
    geojson_domain = 'Default'
    table_id = 0
    validation_status = True

    # this does not work now. Because the request is sent to model-run page
    # when it receives request. This is not in effect. Currently, the request is sent to model_run, not model_input.html
    if request.is_ajax and request.method == 'POST':
        try:
            validation_status, form_error, inputs_dictionary, geojson_files = app_utils.validate_inputs(
                request)  # input_dictionary has proper data type. Not everything string

            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""

        except Exception, e:
            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""
            else:
                form_error = "Error 0: " + str(e)

        if not validation_status:
            # useless code. If the file is prepared, we know validatoin status = False
            import numpy as np
            np.savetxt("/a%s.txt" % form_error, np.array([1, 1]))

        if validation_status:
            pass


    context = {

        'test_function_response': test_function_response,

        'simulation_name': simulation_name,
        'cell_size': cell_size,
        'timestep': timestep,
        'simulation_start_date_picker': simulation_start_date_picker,
        'simulation_end_date_picker': simulation_end_date_picker,
        'timeseries_source': timeseries_source,
        'threshold': threshold,
        'USGS_gage': USGS_gage,
        'model_engine': model_engine,
        'gage_id': id,
        'outlet_x': outlet_x, 'outlet_y': outlet_y,
        'box_topY': box_topY, 'box_rightX': box_rightX, 'box_leftX': box_leftX, 'box_bottomY': box_bottomY,
        'simulation_names_list': simulation_names_list,
        'existing_sim_res_id': existing_sim_res_id,
        'outlet_hs': outlet_hs,
        'bounding_box_hs': bounding_box_hs,

        'form_error': form_error,
        'validation_status': validation_status,
        'model_inputs_table_id': table_id,
        'geojson_outlet': geojson_outlet,
        'geojson_domain': geojson_files,

        'init_soil_percentsat':init_soil_percentsat,
        'init_overland_vol': init_overland_vol,
        'init_channel_flow': init_channel_flow,

        'epsgCode':epsgCode,

        'threshold_topnet': threshold_topnet,
        'pk_min_threshold': pk_min_threshold,
        'pk_max_threshold': pk_max_threshold,
        'pk_num_thershold': pk_num_thershold,
    }

    return render(request, 'hydrotop/model_input.html', context)


def model_run(request):
    """
    Controller that will display the run result (hydrograph). Also allows user to rerun model based on modifications

    *** Confusing Variables & Terms definition:***
    Method I: Preparing the model for the first time froom the GUI
    Method II: Loading the existing model by giving hsID of the model instant, or using dropdown menu (queries db)
    Method III: Modifying the loaded model result

    hs_resource_id_created      : hs resource id created by method I, II or III

    # used in controllers.py to identify from which form the request is coming from.
    model_input_prepare_request : hs resource id created (method I)
    model_input_load_request    : hs resource id created (method II)
    model_input_calib_request   : hs resource id created (method III)

    # used in html to identify where the request is coming from. Default values = None
    hs_resource_id_prepared     : hs resource id created (method I)
    hs_resource_id_loaded       : hs resource id loaded (method II)
    hs_resource_id_modified     : hs resource id modified (method III)

    """
    user_name = request.user.username
    OAuthHS = get_OAuthHS(request)
    user_name = OAuthHS['user_name']

    # INITIAL VARIABLES
    # model_input_load_request = hs_resource_id_loaded = request.GET.get('res_id', None)

    # Defaults
    test_string = "Test_string_default"
    test_variable = "Test_variable_default"
    fac_L_form = ""
    simulation_name = ""
    outlet_y = ""
    outlet_x = ""

    hydrograph_series_obs = None
    hydrograph_series_sim = None
    hydrograph_opacity = 0.1
    observed_hydrograph = ""
    observed_hydrograph2 = ''
    observed_hydrograph3 = ''
    vol_bal_graphs = ''

    observed_hydrograph_userModified = ""
    observed_hydrograph_userModified2 = ""
    observed_hydrograph_userModified3 = ""
    vol_bal_graphs_userModified = ''

    observed_hydrograph_loaded = ""
    observed_hydrograph_loaded2 = ""
    observed_hydrograph_loaded3 = ""
    vol_bal_graphs_loaded = ''

    eta_ts_obj = eta_ts_obj_modified = eta_ts_obj_loaded = ''
    vo_ts_obj = vo_ts_obj_modified = vo_ts_obj_loaded = ''
    vc_ts_obj = vc_ts_obj_modified = vc_ts_obj_loaded = ''
    vs_ts_obj = vs_ts_obj_modified = vs_ts_obj_loaded = ''
    ppt_ts_obj = ppt_ts_obj_modified = ppt_ts_obj_loaded = ''

    model_run_hidden_form = ''
    model_input_prepare_request = None
    hs_resource_id_created = ''
    hs_resource_id_loaded = ''
    hs_resource_id_modified = ''

    simulation_loaded_id = ""
    current_model_inputs_table_id = 0
    model_inputs_table_id_from_another_html = 0  #:TODO need to make it point to last sim by default

    # if user wants to download the file only
    download_response = {}
    hs_res_downloadfile = ''
    download_status = download_response['download_status'] = None  # False
    download_link = download_response['download_link'] = 'http://link.to.zipped.files'
    hs_res_created = download_response['hs_res_created'] = ''
    files_created_dict = 'No dict created'
    download_choice = []
    model_engine_chosen = None

    # initial values
    fac_L_init = fac_Ks_init = fac_n_o_init = fac_n_c_init = fac_th_s_init = 1.0
    pvs_t0_init = 10.0
    vo_t0_init = 5.0
    qc_t0_init = 1.0
    kc_init = 1.0

    # test
    if request.is_ajax and request.method == 'POST':
        pass

    '''
    model_run can receive request from three sources:
    1) model_input, prepare model     (if model_input_prepare_request != None)
    2) model_input, load model        (if model_input_load_request != None)
    3) model_run, calibrate and change the result seen. i.e. passes to itself   (if model_run_calib_request != None)
    '''

    # # check to see if the request is from method (1)
    try:
        model_input_prepare_request = request.POST['simulation_name']
        print "MSG from I: Preparing model simulation, simulation name is: ", model_input_prepare_request
    except:
        model_input_prepare_request = None

    # # check to see if the request is from method (2)
    try:
        # for the input text
        try:
            model_input_load_request = hs_resource_id_created = request.POST['existing_sim_res_id']
            print "MSG from II: Previous simulation is loaded.the simulation loaded from hs_res_id from text box is.", hs_resource_id_created

            if hs_resource_id_created == "":
                model_input_load_request = hs_resource_id_created = request.POST['simulation_names_list']
                print "MSG from II: Previous simulation is loaded. The name of simulation loaded is: ", hs_resource_id_created

        # for the drop down list
        except:
            model_input_load_request = hs_resource_id_created = request.POST['simulation_names_list']  # from drop down menu
            b = request.POST['load_simulation_name']
            print 'MSG from II: The name of simulation loaded from dropdown menu is: ', hs_resource_id_created
            print "MSG from II: Previous simulation is loaded. The name of simulation loaded is: ", hs_resource_id_created
    except:
        # loading from URL
        model_input_load_request = hs_resource_id_loaded = request.GET.get('res_id', None)
        if hs_resource_id_loaded == None: #model_input_load_request = hs_resource_id_loaded = request.GET.get('res_id', None)
            model_input_load_request = None

    # # check to see if the request is from method (3)
    try:
        model_run_calib_request = request.POST['fac_L']
        print 'MSG: Calibration parameters are modified'
    except:
        model_run_calib_request = None






    # Method (1), request from model_input-prepare model
    if model_input_prepare_request != None:
        print 'MSG: Method I initiated.'

        # Checks the model chosen
        model_engine_chosen = request.POST['model_engine']

        if model_engine_chosen.lower() == 'download':  # request.POST.getlist('download_choice2[]') != []:
            print 'User action: DOWNLOAD'

            download_choice = request.POST.getlist('download_choice2[]')

            print 'download_choice(s)=', download_choice

            inputs_dictionary = app_utils.create_model_input_dict_from_request(request, user_name)

            json_data = { u'output_response_txt': u'http://129.123.9.159:20199/files/data/user_6/eg-metadata.txt',
                          u'output_zipfile': u'http://129.123.9.159:20199/files/data/user_6/eg-output.zip',
                          u'output_json_string': {'hs_res_id_created': 'egresid123456'} }

            json_data = app_utils.download_geospatial_and_forcing_files(inputs_dictionary,
                                                                        download_request=download_choice,
                                                                        OAuthHS=OAuthHS)

            print "Downloading all the files successfully completed"

            if json_data != {}:
                download_status = True
                download_link = json_data['output_zipfile']
                hs_res_downloadfile = json_data['output_json_string']['hs_res_id_created']

            # db
            try:
                # Writing to model_inputs_table
                current_model_inputs_table_id = app_utils.write_to_model_input_table(
                    inputs_dictionary=inputs_dictionary, hs_resource_id=hs_res_downloadfile)
            except Exception, e:
                print "Error ---> Writing to DB", e

        elif model_engine_chosen.lower() == 'topnet':
            print 'User action: TOPNET'

            inputs_dictionary = app_utils.create_model_input_dict_from_request(request, user_name)

            json_data = { u'output_response_txt': u'http://129.123.9.159:20199/files/data/user_6/eg-metadata.txt',
                          u'download_link': u'http://129.123.9.159:20199/files/data/user_6/eg-output.zip',
                          u'hs_res_id_created': '4b2e130625464232bd3a58c886eb8fc6' }

            json_data = app_utils.run_topnet(inputs_dictionary, OAuthHS)


            print "Preparing TOPNET input-files completed successfully. The response dict json_data = ",json_data

            if json_data != {}:
                # same output as Download files
                download_status = True
                download_link = json_data['download_link']
                hs_res_downloadfile = json_data['hs_res_id_created']

            # db
            try:
                # Writing to model_inputs_table
                current_model_inputs_table_id = app_utils.write_to_model_input_table(
                    inputs_dictionary=inputs_dictionary, hs_resource_id=hs_res_downloadfile)
            except Exception, e:
                print "Error ---> Writing to DB", e

        elif model_engine_chosen.lower() == 'topkapi':
            print 'User action: topkapi'

            # # Method (1), STEP (1): get input dictionary from request ( request I)
            inputs_dictionary = app_utils.create_model_input_dict_from_request(request, user_name)
            test_string = str("Prepared  Values: ") + str(inputs_dictionary)
            simulation_name = inputs_dictionary['simulation_name']
            print "MSG: Inputs from user read"

            # # Method (1), STEP (2):call_runpytopkapi function
            response_JSON_file = '/home/prasanna/tethysdev/tethysapp-hydrotop/tethysapp/hydrotop/workspaces/user_workspaces/d1785b759e454ab3a67e3999dc74d813/pytopkpai_responseJSON.txt'
            response_JSON_file = app_utils.call_runpytopkapi(inputs_dictionary=inputs_dictionary, OAuthHS=OAuthHS)

            json_data = app_utils.read_data_from_json(response_JSON_file)

            print 'MSG: Prepared Simulation Hydrograph ...'

            hs_resource_id_created = json_data['hs_res_id_created']
            hydrograph_series_obs = json_data['hydrograph_series_obs']
            hydrograph_series_sim = json_data['hydrograph_series_sim']

            eta = json_data['eta']
            vo = json_data['vo']
            vc = json_data['vc']
            vs = json_data['vs']
            ppt = json_data['ppt']

            ppt_cum = json_data['ppt_cum']  # cumulative
            eta_cum = json_data['eta_cum']
            q_obs_cum = json_data['q_obs_cum']
            q_sim_cum = json_data['q_sim_cum']

            # initial values
            # calib_parameter= {"fac_l": 1.0, "fac_n_o": 1.0, "fac_n_c": 1.0, "fac_th_s": 1.0, "fac_ks": 1.0},
            # numeric_param= {"pvs_t0": 50, "vo_t0": 750.0, "qc_t0": 0.0, "kc": 1.0},
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

            print 'hs_resource_id_created =', hs_resource_id_created
            # print [i[-1] for i in hydrograph_series_sim]
            # hydrograph_series_obs = np.nan_to_num(hydrograph_series_obs).tolist()

            # replace nan values to 0 because Tethys timeseries cannot display nan
            hydrograph_series_obs = [[item[0], 0] if np.isnan(item[-1]) else item for item in hydrograph_series_obs]

            # db
            try:
                try:
                    data_qsim_qobs = zip([i[0] for i in hydrograph_series_sim], [i[-1] for i in hydrograph_series_sim],
                                         [i[-1] for i in hydrograph_series_obs])
                except:
                    data_qsim_qobs = zip([i[0] for i in hydrograph_series_sim], [i[-1] for i in hydrograph_series_sim])

                # Writing to model_inputs_table
                current_model_inputs_table_id = app_utils.write_to_model_input_table(
                    inputs_dictionary=inputs_dictionary, hs_resource_id=hs_resource_id_created)

                # Writing to model_calibraiton_table (Because it is first record of the simulation)
                # IF the model did not run, or if user just wants the files, we don't write to calibration table
                current_model_calibration_table_id = app_utils.write_to_model_calibration_table(
                    model_input_table_id=current_model_inputs_table_id,
                    numeric_parameters_list=[pvs_t0_init, vo_t0_init, qc_t0_init, kc_init],
                    calibration_parameters_list=[fac_L_init, fac_Ks_init, fac_n_o_init, fac_n_c_init, fac_th_s_init])

                # Writing to model_result_table :TODO change this, and write only error measuring the results?
                current_model_result_table_id = app_utils.write_to_model_result_table(
                    model_calibration_table_id=current_model_calibration_table_id,
                    timeseries_discharge_list=data_qsim_qobs)

            except Exception, e:
                print "Error ---> Writing to DB", e

            observed_hydrograph3 = TimeSeries(
                height='300px', width='500px', engine='highcharts',
                title="Simulated and Observed Hydrographs",
                subtitle='Nash value: %s, R2: %s' % (json_data['nash_value'], json_data['r2_value']),
                y_axis_title='Discharge ',
                y_axis_units='cfs',
                series=[{
                    'name': 'Simulated Hydrograph',
                    'data': hydrograph_series_sim,
                    'fillOpacity': hydrograph_opacity,
                }, {
                    'name': 'Observed Hydrograph',
                    'data': hydrograph_series_obs,
                    'fillOpacity': hydrograph_opacity,
                }])

            vol_bal_graphs = TimeSeries(
                height='600px', width='500px', engine='highcharts',
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

            eta_ts_obj = app_utils.create_1d(timeseries_list=eta, label='Actual Evapotranspiration', unit='mm/day')
            vc_ts_obj = app_utils.create_1d(timeseries_list=vc, label='Average Water Volume in Channel Cells',
                                            unit='mm/day')
            vs_ts_obj = app_utils.create_1d(timeseries_list=vs, label='Average Water Volume in Soil Cells',
                                            unit='mm/day')
            vo_ts_obj = app_utils.create_1d(timeseries_list=vo, label='Average Water Volume in Overland Cells',
                                            unit='mm/day')
            ppt_ts_obj = app_utils.create_1d(timeseries_list=ppt, label='Rainfall', unit='mm/day')

    # Method (2), request from model_input-load simulation
    if model_input_load_request != None:
        hs_resource_id = model_input_load_request

        print 'MSG: Method II initiated.'
        print 'MSG: Model run for HydroShare resource ID ', hs_resource_id, " is being retreived.."

        # # STEP1: Retrieve simulation information (files stored in HydroShare) from db in a dict
        # inputs_dictionary = app_utils.create_model_input_dict_from_db( hs_resource_id= hs_resource_id,user_name= user_name )
        # test_string = str("Loaded  Values: ")+str(inputs_dictionary)



        ######### START: need to get two variables: i) hs_resource_id_created, and ii) hydrograph series ##############
        response_JSON_file = '/home/prasanna/tethysdev/hydrotop/tethysapp/hydrotop/workspaces/user_workspaces/1b6ba76c8b5641fbb5c436b7de8a521d/pytopkpai_responseJSON.txt'
        response_JSON_file = app_utils.loadpytopkapi(hs_res_id=hs_resource_id,  OAuthHS=OAuthHS, out_folder='')
        json_data = app_utils.read_data_from_json(response_JSON_file)

        hs_resource_id_created = hs_resource_id_loaded = hs_resource_id  # json_data['hs_res_id_created']





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

        observed_hydrograph_loaded = TimeSeries(
            height='300px', width='500px', engine='highcharts', title=' Simulated Hydrograph ',
            subtitle="Simulated and Observed flow  ",
            y_axis_title='Discharge', y_axis_units='cfs',
            series=[{
                'name': 'Simulated Flow',
                'data': hydrograph_series_sim
            }])

        observed_hydrograph_loaded2 = TimeSeries(
            height='500px', width='500px', engine='highcharts', title='Observed (actual) Hydrograph ',
            subtitle="Simulated and Observed flow  ",
            y_axis_title='Discharge', y_axis_units='cfs',
            series=[{
                'name': 'Simulated Flow',
                'data': hydrograph_series_obs
            }])

        observed_hydrograph_loaded3 = TimeSeries(
            height='300px',
            width='500px',
            engine='highcharts',
            title="Simulated and Observed flow  ",
            subtitle='Nash value: %s, R2: %s' % (json_data['nash_value'], json_data['r2_value']),
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

        vol_bal_graphs_loaded = TimeSeries(
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

        vc_ts_obj_loaded = app_utils.create_1d(timeseries_list=vc, label='Average Water Volume in Channel Cells',
                                               unit='mm/day')
        vs_ts_obj_loaded = app_utils.create_1d(timeseries_list=vs, label='Average Water Volume in Soil Cells',
                                               unit='mm/day')
        vo_ts_obj_loaded = app_utils.create_1d(timeseries_list=vo, label='Average Water Volume in Overland Cells',
                                               unit='mm/day')
        ppt_ts_obj_loaded = app_utils.create_1d(timeseries_list=ppt, label='Rainfall', unit='mm/day')
        eta_ts_obj_loaded = app_utils.create_1d(timeseries_list=eta, label='Actual Evapotranspiration', unit='mm/day')


        # STEP2: Because in this part we load previous simulation, Load the model from hydroshare to hydroDS,
        # STEP2: And from the prepeared model, if the result is not available, run. Otherwise just give the result
        # hydrograph2, table_id = app_utils.run_model_with_input_as_dictionary(inputs_dictionary, False)
        # * STEP3: Make sure a string/variable/field remains that contains the id of the model. SO when user modifies it, that model is modifed
        # # STEP4B: Write to db
        # current_model_inputs_table_id = app_utils.write_to_model_input_table(inputs_dictionary,simulation_folder)
        # print "MSG: Inputs from model_input form written to db. Model RAN already"
        # STEP5: get the revised hydrographs, and plot it
        # preparing timeseries data in the format shown in: http://docs.tethysplatform.org/en/latest/tethys_sdk/gizmos/plot_view.html#time-series

        # hydrograph2 = []
        # observed_hydrograph_loaded = ''

    # Method (3), request from model_run, change calibration parameters
    if model_run_calib_request != None:

        fac_L_form = float(request.POST['fac_L'])
        fac_Ks_form = float(request.POST['fac_Ks'])
        fac_n_o_form = float(request.POST['fac_n_o'])
        fac_n_c_form = float(request.POST['fac_n_c'])
        fac_th_s_form = float(request.POST['fac_th_s'])

        pvs_t0_form = float(request.POST['pvs_t0'])
        vo_t0_form = float(request.POST['vo_t0'])
        qc_t0_form = float(request.POST['qc_t0'])
        kc_form = float(request.POST['kc'])

        # model_inputs_table_id_from_another_html = request.POST['model_inputs_table_id_from_another_html']
        hs_resource_id_from_previous_simulation = request.POST['model_inputs_table_id_from_another_html']
        # current_model_inputs_table_id  =hs_resource_id_from_previous_simulation
        hs_resource_id_created = hs_resource_id_from_previous_simulation

        print 'MSG: Method III initiated. The model id we are looking at is: ', hs_resource_id_from_previous_simulation

        ######### START: need to get at leaset two variables: i) hs_resource_id_created, and ii) hydrograph series #####
        response_JSON_file = '/home/prasanna/tethysdev/hydrotop/tethysapp/hydrotop/workspaces/user_workspaces/1b6ba76c8b5641fbb5c436b7de8a521d/pytopkpai_responseJSON.txt'
        response_JSON_file = app_utils.modifypytopkapi(hs_res_id=hs_resource_id_created, OAuthHS=OAuthHS, out_folder='',
                                                       fac_l=fac_L_form, fac_ks=fac_Ks_form, fac_n_o=fac_n_o_form,
                                                       fac_n_c=fac_n_c_form, fac_th_s=fac_th_s_form,
                                                       pvs_t0=pvs_t0_form, vo_t0=vo_t0_form, qc_t0=qc_t0_form,
                                                       kc=kc_form)
        json_data = app_utils.read_data_from_json(response_JSON_file)

        hs_resource_id_created = hs_resource_id_modified = json_data['hs_res_id_created']
        hydrograph_series_sim = json_data['hydrograph_series_sim']
        hydrograph_series_obs = json_data['hydrograph_series_obs']
        eta = json_data['eta']
        ppt = json_data['ppt']
        vo = json_data['vo']
        vc = json_data['vc']
        vs = json_data['vs']

        ppt_cum = json_data['ppt_cum']  # cumulative
        eta_cum = json_data['eta_cum']
        q_obs_cum = json_data['q_obs_cum']
        q_sim_cum = json_data['q_sim_cum']

        print 'hydrograph_series_sim is ', [item[-1] for item in hydrograph_series_sim]

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
        print '***hs_resource_id_created', hs_resource_id_created
        # print [i[-1] for i in hydrograph_series_sim]
        ######### END :  ###############



        # db
        try:
            try:
                data_qsim_qobs = zip([i[0] for i in hydrograph_series_sim], [i[-1] for i in hydrograph_series_sim],
                                     [i[-1] for i in hydrograph_series_obs])
            except:
                data_qsim_qobs = zip([i[0] for i in hydrograph_series_sim], [i[-1] for i in hydrograph_series_sim])

            # Writing to model_inputs_table
            current_model_inputs_table_id = app_utils.get_model_input_id_for_hs_res_id(hs_resource_id_created)

            # Writing to model_calibraiton_table (Because it is first record of the simulation)
            # IF the model did not run, or if user just wants the files, we don't write to calibration table
            current_model_calibration_table_id = app_utils.write_to_model_calibration_table(
                model_input_table_id=current_model_inputs_table_id,
                numeric_parameters_list=[pvs_t0_init, vo_t0_init, qc_t0_init, kc_init],
                calibration_parameters_list=[fac_L_init, fac_Ks_init, fac_n_o_init, fac_n_c_init, fac_th_s_init])

            # Writing to model_result_table :TODO change this, and write only error measuring the results?
            current_model_result_table_id = app_utils.write_to_model_result_table(
                model_calibration_table_id=current_model_calibration_table_id,
                timeseries_discharge_list=data_qsim_qobs)

        except Exception, e:
            print "Error ---> Writing to DB", e



        # # # -------DATABASE STUFFS  <start>----- # #
        # # retreive the model_inputs_table.id of this entry to pass it to the next page (calibration page)
        # from .model import engine, SessionMaker, Base, model_calibration_table
        # session = SessionMaker()                # Make session
        #
        # # STEP1: retrieve the model_inputs_table.id of this entry to pass it to the next page (calibration page)
        # current_model_inputs_table_id = str(len(session.query(model_inputs_table).filter(
        #                                             model_inputs_table.user_name == user_name).all()))  # because PK is the same as no of rows, i.e. length
        #
        # # STEP2: use the id retrieved in STEP1 to get all the remaining parameters
        # print 'model_input ID for which rest of the inputs are being retrieved: ', current_model_inputs_table_id
        #
        # all_rows = session.query(model_inputs_table).filter(model_inputs_table.id == current_model_inputs_table_id).all()
        #
        # # retrieve the parameters and write to a dictionary
        # inputs_dictionary = {}
        #
        # for row in all_rows:
        #     inputs_dictionary['id'] = row.id
        #     inputs_dictionary['user_name'] = row.user_name
        #     inputs_dictionary['simulation_name'] = row.simulation_name
        #     inputs_dictionary['simulation_folder'] = row.simulation_folder
        #     inputs_dictionary['simulation_start_date'] = row.simulation_start_date
        #     inputs_dictionary['simulation_end_date'] = row.simulation_end_date
        #     inputs_dictionary['USGS_gage'] = row.USGS_gage
        #
        #     inputs_dictionary['outlet_x'] = row.outlet_x
        #     inputs_dictionary['outlet_y'] = row.outlet_y
        #     inputs_dictionary['box_topY'] = row.box_topY
        #     inputs_dictionary['box_bottomY'] = row.box_bottomY
        #     inputs_dictionary['box_rightX'] = row.box_rightX
        #     inputs_dictionary['box_leftX'] = row.box_leftX
        #
        #     timeseries_source,threshold, cell_size,timestep =  row.other_model_parameters.split("__")
        #     inputs_dictionary['timeseries_source'] = timeseries_source
        #     inputs_dictionary['threshold'] = threshold
        #     inputs_dictionary['cell_size'] = cell_size
        #     inputs_dictionary['timestep'] = timestep
        #
        #     inputs_dictionary['model_engine'] = row.model_engine


        observed_hydrograph_userModified3 = TimeSeries(
            height='300px',
            width='500px',
            engine='highcharts',
            title="Simulated and Observed flow ",
            subtitle='Nash value: %s, R2: %s' % (json_data['nash_value'], json_data['r2_value']),
            y_axis_title='Discharge ',
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

        observed_hydrograph_userModified = TimeSeries(
            height='300px',
            width='500px',
            engine='highcharts',
            title=' Corrected Hydrograph ',
            subtitle="Simulated and Observed flow ",
            y_axis_title='Discharge',
            y_axis_units='cfs',
            series=[{
                'name': 'Simulated Flow',
                'data': hydrograph_series_sim
            }]
        )

        observed_hydrograph_userModified2 = TimeSeries(
            height='500px', width='500px', engine='highcharts', title=' Observed (Actual) Hydrograph ',
            subtitle="Simulated and Observed flow ",
            y_axis_title='Discharge', y_axis_units='cfs',
            series=[{
                'name': 'Observed Flow',
                'data': hydrograph_series_obs
            }])

        vol_bal_graphs_userModified = TimeSeries(
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

        vc_ts_obj_modified = app_utils.create_1d(timeseries_list=vc, label='Average Water Volume in Channel Cells',
                                                 unit='mm/day')
        vs_ts_obj_modified = app_utils.create_1d(timeseries_list=vs, label='Average Water Volume in Soil Cells',
                                                 unit='mm/day')
        vo_ts_obj_modified = app_utils.create_1d(timeseries_list=vo, label='Average Water Volume in Overland Cells',
                                                 unit='mm/day')
        ppt_ts_obj_modified = app_utils.create_1d(timeseries_list=ppt, label='Rainfall', unit='mm/day')
        eta_ts_obj_modified = app_utils.create_1d(timeseries_list=eta, label='Actual Evapotranspiration', unit='mm/day')







    print 'simulation_loaded_id', simulation_loaded_id  # probably useless
    print 'hs_resource_id_created', hs_resource_id_created

    print 'hs_resource_id_prepared', model_input_prepare_request
    print 'hs_resource_id_loaded', model_input_load_request
    print 'hs_resource_id_modified', model_run_calib_request

    # gizmo settings
    fac_L = TextInput(display_text='Soil depth across all model cells', name='fac_L', initial=float(fac_L_init))
    fac_Ks = TextInput(display_text='Saturated hydraulic conductivity', name='fac_Ks', initial=float(fac_Ks_init))
    fac_n_o = TextInput(display_text="Manning's n for overland", name='fac_n_o', initial=float(fac_n_o_init))
    fac_n_c = TextInput(display_text="Manning's n for channel", name='fac_n_c', initial=float(fac_n_c_init))
    fac_th_s = TextInput(display_text='Soil saturation', name='fac_th_s', initial=float(fac_th_s_init))

    pvs_t0 = TextInput(display_text="Soil cell's saturation %", name='pvs_t0', initial=float(pvs_t0_init))
    vo_t0 = TextInput(display_text="Water volume in Overland cells (m3)", name='vo_t0', initial=float(vo_t0_init))
    qc_t0 = TextInput(display_text='Flow in channel cells (m3/s)', name='qc_t0', initial=float(qc_t0_init))
    kc = TextInput(display_text='Crop coefficient across all model cells', name='kc', initial=float(kc_init))

    context = {'simulation_name': simulation_name,
               'outlet_y': outlet_y,
               'outlet_x': outlet_x,

               'fac_L': fac_L, 'fac_Ks': fac_Ks, 'fac_n_o': fac_n_o, "fac_n_c": fac_n_c, "fac_th_s": fac_th_s,
               'pvs_t0': pvs_t0, 'vo_t0': vo_t0, 'qc_t0': qc_t0, "kc": kc,

               'fac_L_form': fac_L_form,
               'user_name': user_name,

               # 'Iwillgiveyou_model_inputs_table_id_from_another_html':model_inputs_table_id_from_another_html,
               # "current_model_inputs_table_id":current_model_inputs_table_id, # model_inputs_table_id

               'observed_hydrograph3': observed_hydrograph3,
               'observed_hydrograph': observed_hydrograph,
               'observed_hydrograph2': observed_hydrograph2,

               "observed_hydrograph_userModified": observed_hydrograph_userModified,
               "observed_hydrograph_userModified2": observed_hydrograph_userModified2,
               "observed_hydrograph_userModified3": observed_hydrograph_userModified3,

               "observed_hydrograph_loaded": observed_hydrograph_loaded,
               "observed_hydrograph_loaded2": observed_hydrograph_loaded2,
               "observed_hydrograph_loaded3": observed_hydrograph_loaded3,

               'eta_ts_obj': eta_ts_obj,
               'vs_ts_obj': vs_ts_obj,
               'vc_ts_obj': vc_ts_obj,
               'vo_ts_obj': vo_ts_obj,
               'ppt_ts_obj': ppt_ts_obj,
               'vol_bal_graphs': vol_bal_graphs,

               'eta_ts_obj_modified': eta_ts_obj_modified,
               'vs_ts_obj_modified': vs_ts_obj_modified,
               'vc_ts_obj_modified': vc_ts_obj_modified,
               'vo_ts_obj_modified': vo_ts_obj_modified,
               'ppt_ts_obj_modified': ppt_ts_obj_modified,
               'vol_bal_graphs_userModified': vol_bal_graphs_userModified,

               'eta_ts_obj_loaded': eta_ts_obj_loaded,
               'vs_ts_obj_loaded': vs_ts_obj_loaded,
               'vc_ts_obj_loaded': vc_ts_obj_loaded,
               'vo_ts_obj_loaded': vo_ts_obj_loaded,
               'ppt_ts_obj_loaded': ppt_ts_obj_loaded,
               'vol_bal_graphs_loaded': vol_bal_graphs_loaded,

               "simulation_loaded_id": simulation_loaded_id,
               'test_string': simulation_loaded_id,  # test_string
               'test_variable': test_variable,

               'hs_resource_id_created': hs_resource_id_created,

               'hs_resource_id_prepared': model_input_prepare_request,
               'hs_resource_id_loaded': model_input_load_request,
               'hs_resource_id_modified': model_run_calib_request,

               # fow download request
               'hs_res_downloadfile': hs_res_downloadfile,
               'download_status': download_status,
               'download_link': download_link,
               'hs_res_created': hs_res_created,
               'dict_files_created': files_created_dict,

               'model_engine_chosen':model_engine_chosen,
               }

    return render(request, 'hydrotop/model-run.html', context)


def visualize_shp(request):
    # when it receives request. This is not in effect. Currently, the request is sent to model_run, not model_input.html
    geojson_files = {}
    geojson_domain = ''
    if request.is_ajax and request.method == 'POST':
        print "Request Received"

        for afile in request.FILES.getlist('watershed_upload'):

            if afile.name.split(".")[-1] == "shp":
                watershed_upload = afile
            if afile.name.split(".")[-1] == "shx":
                watershed_shx = afile
            if afile.name.split(".")[-1] == "prj":
                watershed_prj = afile
            if afile.name.split(".")[-1] == "dbf":
                watershed_dbf = afile

        # lines below are not being executed
        # box_rightX, box_bottomY, box_leftX, box_topY = get_box_xyxy_from_shp_shx(shp_file=watershed_upload,shx_file=watershed_shx)
        geojson_files['geojson_domain'] = app_utils.shapefile_to_geojson(watershed_upload)
        print geojson_files

        # validation_status, form_error, inputs_dictionary, geojson_files = app_utils.validate_inputs(request) # input_dictionary has proper data type. Not everything string

        for geojson in geojson_files.keys():
            if geojson == 'geojson_outlet':
                geojson_outlet = geojson_files['geojson_outlet']
                print geojson_outlet
            if geojson == 'geojson_domain':
                geojson_domain = geojson_files['geojson_domain']
                print geojson_domain

    context = {

        'geojson_file': geojson_domain
    }

    return render(request, 'hydrotop/model_input.html', context)


def google_map_input(request):
    context = {}
    return render(request, 'hydrotop/googlemap.html', context)


def tables(request):

    try:
        OAuthHS = get_OAuthHS(request)
        user_name = OAuthHS['user_name']
    except:
        user_name = request.user.username

    test_string = None
    hs_res_id_for_table = None
    calib_id_queried = None
    calibration_list = None


    # DROPDOWN 1, TABLE1
    simulation_names_list = app_utils.create_model_input_list(given_user_name=user_name)
    table_model_input = app_utils.create_tethysTableView_simulationRecord(user_name)

    # when request is sent
    if request.is_ajax and request.method == 'POST':
        hs_res_queried = request.POST['simulation_names_list']
        print 'hs_res_queried', hs_res_queried

        # TABLE2: calibration ----FOR----> selected hs_res
        table_model_calibration = app_utils.create_tethysTableView_calibrationRecord(hs_resource_id=hs_res_queried)

        # TABLE3: model result ----FOR----> selected hydroshare resource
        table_model_result = app_utils.create_tethysTableView_timeseries_for_hs_res(hs_resource_id=hs_res_queried)

        # # DROPDOWN 2
        # create a drop down query of all the calibration ids for the selected model_input id.
        # model_calib_ids_for_model_input_id = [item[0] for item in table_model_calibration.rows]
        # calibration_list = app_utils.create_calibration_list( hs_resource_id=hs_res_queried)  # (calib_ids = model_calib_ids_for_model_input_id)

    else:
        hs_res_queried = None
        table_model_calibration = None
        table_model_result = None

    # TABLES 4,5. **NOT DISPLAYED**
    table_model_input_ALL = app_utils.create_tethysTableView_EntireRecord(table_name='model_input')
    table_model_calibration_ALL = app_utils.create_tethysTableView_EntireRecord(table_name='calibration')
    # table_model_result_ALL  = app_utils.create_tethysTableView_EntireRecord(table_name='result') # this will slow down the computer



    context = {
        'test_string1': test_string,

        'hs_res_queried':hs_res_queried,
        'calib_id_queried':calib_id_queried,

        'simulation_names_list':simulation_names_list,
        'calibration_list':calibration_list,
        'hs_res_id_for_table':hs_res_id_for_table,

        'table_model_input': table_model_input,
        'table_model_calibration': table_model_calibration,
        'table_model_result':table_model_result,

        'table_model_input_ALL':table_model_input_ALL,
        'table_model_calibration_ALL':table_model_calibration_ALL,
        # 'table_model_result_ALL':table_model_result_ALL,
    }
    return render(request, 'hydrotop/tables.html', context)

def model_input1(request):
    user_name = request.user.username
    OAuthHS = get_OAuthHS(request)
    user_name = OAuthHS['user_name']

    # Define Gizmo Options
    # from .model import engine, SessionMaker, Base, model_inputs_table, model_calibration_table

    # Query DB for gage objects, all the entries by the user name
    # give the value for thsi variable = 0 if the program is starting for the first time
    simulation_names_list = app_utils.create_simulation_list_after_querying_db(given_user_name=user_name)

    # init_channel_flow, init_overland_vol, init_soil_percentsat
    # # intials
    watershed_name = 'Plunge'  # 'RBC' , 'Santa Cruz', 'Barrow Creeks', 'Plunge' , Logan
    initials = {

        'Logan': {'simulation_name': 'Logan_sample', 'USGS_gage': '10109000', 'cell_size': '30', 't0': '10-01-2010',
                  't': '10-30-2010', 'threshold': '25', 'del_t': '24', 'x': '-111.7836', 'y': '41.7436',
                  'ymax': '42.12', 'xmax': '-111.44', 'ymin': '41.68', 'xmin': '-111.83' ,
                  'init_soil_percentsat':'30' },

        'RBC': {'simulation_name': 'RBC_sample', 'USGS_gage': '10172200', 'cell_size': '100', 't0': '10-01-2010',
                't': '10-03-2011', 'threshold': '2', 'del_t': '24', 'x': '-111.80624', 'y': '40.77968',
                'ymax': '40.8327', 'xmax': '-111.728', 'ymin': '40.772', 'xmin': '-111.834',
                'init_soil_percentsat': '30'},

        'Plunge': {'simulation_name': 'Plunge_demo', 'USGS_gage': '11055500', 'cell_size': '100', 't0': '10-01-2010',
                   't': '10-01-2011', 'threshold': '5', 'del_t': '24', 'x': '-117.141284', 'y': '34.12128',
                   # 'ymax':'34.2336', 'xmax': '-117.048046', 'ymin': '34.10883', 'xmin': '-117.168289',
                   'ymax': '34.23', 'xmax': '-117.1', 'ymin': '34.10883', 'xmin': '-117.2',
                   'init_soil_percentsat': '30'
                   },

        'SantaCruz': {'simulation_name': 'SantaCruz_demo', 'USGS_gage': '11124500', 'cell_size': '500',
                      't0': '10-01-2010',
                      't': '10-01-2011', 'threshold': '5', 'del_t': '24', 'x': '-119.90873', 'y': '34.59637',
                      'ymax': '34.714', 'xmax': '-119.781', 'ymin': '34.586', 'xmin': '-119.925',
                      'init_soil_percentsat': '30'},


        'SanMarcos': {'simulation_name': 'SANMARCOS_TX_2010', 'USGS_gage': '11028500', 'cell_size': '100',
                       't0': '10-01-2010',
                       't': '10-01-2011', 'threshold': '15', 'del_t': '24', 'x': '-116.9455844', 'y': '33.0522655',
                       'ymax': '30.213', 'xmax': '-97.956', 'ymin': '30.027', 'xmin': '-97.99',
                       'init_soil_percentsat': '30'},

    }

    simulation_name = TextInput(display_text='Simulation name', name='simulation_name',
                                initial=initials[watershed_name]['simulation_name'])
    USGS_gage = TextInput(display_text='USGS gage nearby', name='USGS_gage',
                          initial=initials[watershed_name]['USGS_gage'])
    cell_size = TextInput(display_text='Cell size in meters', name='cell_size',
                          initial=initials[watershed_name]['cell_size'])
    timestep = TextInput(display_text='Timestep in hrs', name='timestep',
                         initial=initials[watershed_name]['del_t'])  # , append="hours"
    simulation_start_date_picker = DatePicker(name='simulation_start_date_picker', display_text='Start Date',
                                              autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                              # '01-01-2010'
                                              start_view='year', today_button=True,
                                              initial=initials[watershed_name]['t0'])
    simulation_end_date_picker = DatePicker(name='simulation_end_date_picker', display_text='End Date',
                                            autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                            # '01-01-2010'
                                            start_view='year', today_button=False,
                                            initial=initials[watershed_name]['t'])
    threshold = TextInput(display_text='Stream threshold in square km', name='threshold',
                          initial=initials[watershed_name]['threshold'])


    init_soil_percentsat = TextInput(display_text='Intial saturation in soil cells (in %) ', name='init_soil_percentsat',
                          initial=initials[watershed_name]['init_soil_percentsat'])
    init_overland_vol = TextInput(display_text='Intial volume of water in overland cells (in m3) ', name='init_overland_vol',
                          initial=str(  0.0003* float(initials[watershed_name]['cell_size'])**2  ))
    init_channel_flow = TextInput(display_text='Intial flow of water in channel cells (in m3/s) ', name='init_channel_flow',
                          initial=str( float(initials[watershed_name]['cell_size']) * .001) )

    threshold_topnet = TextInput(display_text='Stream threshold', name='threshold_topnet', initial=100)
    pk_min_threshold = TextInput(display_text='pk_min_threshold', name='pk_min_threshold', initial=500)
    pk_max_threshold = TextInput(display_text='pk_max_threshold', name='pk_max_threshold', initial=50000)
    pk_num_thershold = TextInput(display_text='pk_num_thershold', name='pk_num_thershold', initial=12)

    epsgCode = TextInput(display_text='EPSG projection for outputs', name='epsgCode', initial=102003)

    timeseries_source = SelectInput(display_text='Forcing source',
                                    name='timeseries_source',
                                    multiple=False,
                                    options=[('Daymet', 'Daymet'), ('UEB', 'UEB')],
                                    initial=['Daymet'],
                                    original=['Daymet'])


    model_engine = SelectInput(display_text='Choose an action',
                               name='model_engine',
                               multiple=False,
                               options=[('Download geospatial files', 'download'), ('Prepare TOPKAPI model', 'TOPKAPI'),
                                        ('Prepare TOPNET input-files', 'TOPNET')],
                               initial=['download'],
                               original=['download']
                               )

    # # html form to django form

    # (Any Watershed)
    outlet_x = TextInput(display_text='Longitude', name='outlet_x',
                         initial=initials[watershed_name]['x'])  # 41.74025, -111.7915
    outlet_y = TextInput(display_text='Latitude', name='outlet_y', initial=initials[watershed_name]['y'])

    box_topY = TextInput(display_text='North Y', name='box_topY', initial=initials[watershed_name]['ymax'])
    box_rightX = TextInput(display_text='East X', name='box_rightX', initial=initials[watershed_name]['xmax'])
    box_bottomY = TextInput(display_text='South Y', name='box_bottomY', initial=initials[watershed_name]['ymin'])
    box_leftX = TextInput(display_text='West X', name='box_leftX', initial=initials[watershed_name]['xmin'])

    outlet_hs = TextInput(display_text='', name='outlet_hs', initial='')
    bounding_box_hs = TextInput(display_text='', name='bounding_box_hs', initial='')

    existing_sim_res_id = TextInput(display_text='', name='existing_sim_res_id', initial='')

    form_error = ""
    test_function_response = ""
    geojson_files = {}
    geojson_outlet = 'Default'
    geojson_domain = 'Default'
    table_id = 0
    validation_status = True

    # this does not work now. Because the request is sent to model-run page
    # when it receives request. This is not in effect. Currently, the request is sent to model_run, not model_input.html
    if request.is_ajax and request.method == 'POST':
        try:
            validation_status, form_error, inputs_dictionary, geojson_files = app_utils.validate_inputs(
                request)  # input_dictionary has proper data type. Not everything string

            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""

        except Exception, e:
            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""
            else:
                form_error = "Error 0: " + str(e)

        if not validation_status:
            # useless code. If the file is prepared, we know validatoin status = False
            import numpy as np
            np.savetxt("/a%s.txt" % form_error, np.array([1, 1]))

        if validation_status:
            pass


    context = {

        'test_function_response': test_function_response,

        'simulation_name': simulation_name,
        'cell_size': cell_size,
        'timestep': timestep,
        'simulation_start_date_picker': simulation_start_date_picker,
        'simulation_end_date_picker': simulation_end_date_picker,
        'timeseries_source': timeseries_source,
        'threshold': threshold,
        'USGS_gage': USGS_gage,
        'model_engine': model_engine,
        'gage_id': id,
        'outlet_x': outlet_x, 'outlet_y': outlet_y,
        'box_topY': box_topY, 'box_rightX': box_rightX, 'box_leftX': box_leftX, 'box_bottomY': box_bottomY,
        'simulation_names_list': simulation_names_list,
        'existing_sim_res_id': existing_sim_res_id,
        'outlet_hs': outlet_hs,
        'bounding_box_hs': bounding_box_hs,

        'form_error': form_error,
        'validation_status': validation_status,
        'model_inputs_table_id': table_id,
        'geojson_outlet': geojson_outlet,
        'geojson_domain': geojson_files,

        'init_soil_percentsat':init_soil_percentsat,
        'init_overland_vol': init_overland_vol,
        'init_channel_flow': init_channel_flow,

        'epsgCode':epsgCode,

        'threshold_topnet': threshold_topnet,
        'pk_min_threshold': pk_min_threshold,
        'pk_max_threshold': pk_max_threshold,
        'pk_num_thershold': pk_num_thershold,
    }

    return render(request, 'hydrotop/model_input1.html', context)

def job_check(request):
    OAuthHS = get_OAuthHS(request)
    user_name = OAuthHS['user_name']

    try:
        res_id = request.GET.get('res_id', None)
    except:
        pass

    # QUERY HYDROSHARE: list all the resources that are prepared by the model
    hs_model_resources_response = app_utils.create_model_resources_from_hs(OAuthHS)
    hs_model_resources_list = hs_model_resources_response['hs_model_resources_list']
    hs_model_resources_table = app_utils.create_tethysTableView(
                                model_input_cols=('resource_title', 'date_created', 'resource_id',' job_id'),
                                model_input_rows=hs_model_resources_list)

    # QUERY DATABASE: list all the resources that are SENT
    simulation_names_response = app_utils.create_model_run_list_from_db(OAuthHS)
    simulation_names_list = simulation_names_response['db_model_run_list']
    simulation_names_table = app_utils.create_tethysTableView(model_input_cols=('ID', 'Simulation_name'),
                                                               model_input_rows=simulation_names_list)

    last_jobid = app_utils.get_id_from_db(user_name)

    context = {
        'hs_model_resources_list':hs_model_resources_list,
        'hs_model_resources_table':hs_model_resources_table,
        'simulation_names_table':simulation_names_table,
        'last_jobid':last_jobid

    }

    return render(request, 'hydrotop/job_check.html', context)



def model_input0(request):
    user_name = request.user.username

    # Define Gizmo Options
    # from .model import engine, SessionMaker, Base, model_inputs_table, model_calibration_table

    # Query DB for gage objects, all the entries by the user name
    # give the value for thsi variable = 0 if the program is starting for the first time
    simulation_names_list = app_utils.create_simulation_list_after_querying_db(given_user_name=user_name)

    # # intials
    watershed_name = 'SantaCruz'  # 'RBC' , 'Santa Cruz', 'Barrow Creeks', 'Plunge' , Logan
    initials = {

        'Logan': {'simulation_name': 'Logan_sample', 'USGS_gage': '10109000', 'cell_size': '300', 't0': '10-01-2010',
                  't': '10-30-2010', 'threshold': '25', 'del_t': '24', 'x': '-111.7836', 'y': '41.7436',
                  'ymax': '42.12', 'xmax': '-111.44', 'ymin': '41.68', 'xmin': '-111.83'},

        'RBC': {'simulation_name': 'RBC_sample', 'USGS_gage': '10172200', 'cell_size': '100', 't0': '10-01-2010',
                't': '10-03-2011', 'threshold': '2', 'del_t': '24', 'x': '-111.80624', 'y': '40.77968',
                'ymax': '40.8327', 'xmax': '-111.728', 'ymin': '40.772', 'xmin': '-111.834'},

        'Plunge': {'simulation_name': 'Plunge_sample', 'USGS_gage': '11055500', 'cell_size': '300', 't0': '10-01-2010',
                   't': '01-01-2011', 'threshold': '5', 'del_t': '24', 'x': '-117.141284', 'y': '34.12128',
                   # 'ymax':'34.2336', 'xmax': '-117.048046', 'ymin': '34.10883', 'xmin': '-117.168289',
                   'ymax': '34.213', 'xmax': '-117.062', 'ymin': '34.10883', 'xmin': '-117.18'
                   },

        'SantaCruz': {'simulation_name': 'SantaCruz_demo', 'USGS_gage': '11124500', 'cell_size': '500',
                      't0': '11-15-2010',
                      't': '06-15-2011', 'threshold': '5', 'del_t': '24', 'x': '-119.90873', 'y': '34.59637',
                      'ymax': '34.714', 'xmax': '-119.781', 'ymin': '34.586', 'xmin': '-119.925'},

        'BlancoRiver': {'simulation_name': 'BlancoRiver_trial', 'USGS_gage': '08171000', 'cell_size': '500',
                        't0': '01-01-2010',
                        't': '12-30-2011', 'threshold': '20', 'del_t': '24', 'x': '-98.088989', 'y': '29.99349',
                        'ymax': '30.20707', 'xmax': '-98.0679', 'ymin': '29.96298', 'xmin': '-98.4732'},

        'OnionCreek': {'simulation_name': 'OnionCreek_trial', 'USGS_gage': '08158700', 'cell_size': '200',
                       't0': '01-01-2010',
                       't': '12-30-2011', 'threshold': '20', 'del_t': '24', 'x': '-98.00826', 'y': '30.08341',
                       'ymax': '30.213', 'xmax': '-97.956', 'ymin': '30.027', 'xmin': '-98.461'},

    }

    simulation_name = TextInput(display_text='Simulation name', name='simulation_name',
                                initial=initials[watershed_name]['simulation_name'])
    USGS_gage = TextInput(display_text='USGS gage nearby', name='USGS_gage',
                          initial=initials[watershed_name]['USGS_gage'])
    cell_size = TextInput(display_text='Cell size in meters', name='cell_size',
                          initial=initials[watershed_name]['cell_size'])
    timestep = TextInput(display_text='Timestep in hrs', name='timestep',
                         initial=initials[watershed_name]['del_t'])  # , append="hours"
    simulation_start_date_picker = DatePicker(name='simulation_start_date_picker', display_text='Start Date',
                                              autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                              start_view='year', today_button=True,
                                              initial=initials[watershed_name]['t0'])
    simulation_end_date_picker = DatePicker(name='simulation_end_date_picker', display_text='End Date',
                                            autoclose=True, format='mm-dd-yyyy', start_date='10-15-2005',
                                            start_view='year', today_button=False,
                                            initial=initials[watershed_name]['t'])
    threshold = TextInput(display_text='Stream threshold in km2', name='threshold',
                          initial=initials[watershed_name]['threshold'])

    timeseries_source = SelectInput(display_text='Timeseries source',
                                    name='timeseries_source',
                                    multiple=False,
                                    options=[('Daymet', 'Daymet'), ('UEB', 'UEB')],
                                    initial=['Daymet'],
                                    original=['Daymet'])

    model_engine = SelectInput(display_text='Choose Model',
                               name='model_engine',
                               multiple=False,
                               options=[('TOPKAPI', 'TOPKAPI'), ('TOPNET', 'TOPNET')],
                               initial=['TOPKAPI'],
                               original=['TOPKAPI'])

    # # html form to django form

    # (Any Watershed)
    outlet_x = TextInput(display_text='Longitude', name='outlet_x',
                         initial=initials[watershed_name]['x'])  # 41.74025, -111.7915
    outlet_y = TextInput(display_text='Latitude', name='outlet_y', initial=initials[watershed_name]['y'])

    box_topY = TextInput(display_text='North Y', name='box_topY', initial=initials[watershed_name]['ymax'])
    box_rightX = TextInput(display_text='East X', name='box_rightX', initial=initials[watershed_name]['xmax'])
    box_bottomY = TextInput(display_text='South Y', name='box_bottomY', initial=initials[watershed_name]['ymin'])
    box_leftX = TextInput(display_text='West X', name='box_leftX', initial=initials[watershed_name]['xmin'])

    outlet_hs = TextInput(display_text='', name='outlet_hs', initial='')
    bounding_box_hs = TextInput(display_text='', name='bounding_box_hs', initial='')

    existing_sim_res_id = TextInput(display_text='', name='existing_sim_res_id', initial='')

    form_error = ""
    observed_hydrograph = ""
    test_function_response = ""
    geojson_files = {}
    geojson_outlet = 'Default'
    geojson_domain = 'Default'
    table_id = 0
    validation_status = True

    # when it receives request. This is not in effect. Currently, the request is sent to model_run, not model_input.html
    if request.is_ajax and request.method == 'POST':
        try:
            validation_status, form_error, inputs_dictionary, geojson_files = app_utils.validate_inputs(
                request)  # input_dictionary has proper data type. Not everything string
            # if geojson_files != {}:
            #     for geojson in geojson_files.keys():
            #         if geojson == 'geojson_outlet':
            #             geojson_outlet = geojson_files['geojson_outlet']
            #         if geojson == 'geojson_domain':
            #             geojson_domain = geojson_files['geojson_domain']


            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""

        except Exception, e:
            if form_error.startswith("Error 2") or form_error.startswith(
                    "Error 3"):  # may not need this part. Because if no shapefile input, will not read it
                form_error = ""
            else:
                form_error = "Error 0: " + str(e)

        if not validation_status:
            # useless code. If the file is prepared, we know validatoin status = False
            import numpy as np
            np.savetxt("/a%s.txt" % form_error, np.array([1, 1]))

        if validation_status:
            # hydrograpph series is a series (list) object.
            # table_id is the id of the data just written in the database after the successful model run
            hydrograph_series = []
            # hydrograph_series, table_id = app_utils.run_model_with_input_as_dictionary(inputs_dictionary,False, simulation_folder="")


            observed_hydrograph = TimeSeries(
                height='500px',
                width='500px',
                engine='highcharts',
                title='Hydrograph ',
                subtitle="Simulated and Observed flow for " + inputs_dictionary['simulation_name'],
                y_axis_title='Discharge',
                y_axis_units='cumecs',
                series=[{
                    'name': 'Simulated Flow',
                    'data': hydrograph_series,
                }]
            )

    context = {

        'test_function_response': test_function_response,
        "observed_hydrograph": observed_hydrograph,

        'simulation_name': simulation_name,
        'cell_size': cell_size,
        'timestep': timestep,
        'simulation_start_date_picker': simulation_start_date_picker,
        'simulation_end_date_picker': simulation_end_date_picker,
        'timeseries_source': timeseries_source,
        'threshold': threshold,
        'USGS_gage': USGS_gage,
        'model_engine': model_engine,
        'gage_id': id,
        'outlet_x': outlet_x, 'outlet_y': outlet_y,
        'box_topY': box_topY, 'box_rightX': box_rightX, 'box_leftX': box_leftX, 'box_bottomY': box_bottomY,
        'simulation_names_list': simulation_names_list,
        'existing_sim_res_id': existing_sim_res_id,
        'outlet_hs': outlet_hs,
        'bounding_box_hs': bounding_box_hs,

        'form_error': form_error,
        'validation_status': validation_status,
        'model_inputs_table_id': table_id,
        'geojson_outlet': geojson_outlet,
        'geojson_domain': geojson_files,

    }

    return render(request, 'hydrotop/model-input0.html', context)




# get hs object through oauth
def get_OAuthHS(request):
    OAuthHS = {}
    OAuthHS['user_name'] = request.user.username

    try:
        hs_hostname = "www.hydroshare.org"

        client_id = getattr(settings, "SOCIAL_AUTH_HYDROSHARE_KEY", None)
        client_secret = getattr(settings, "SOCIAL_AUTH_HYDROSHARE_SECRET", None)

        # this line will throw out from django.core.exceptions.ObjectDoesNotExist if current user is not signed in via HydroShare OAuth
        token = request.user.social_auth.get(provider='hydroshare').extra_data['token_dict']
        user_name = request.user.social_auth.get(provider='hydroshare').uid

        auth = HydroShareAuthOAuth2(client_id, client_secret, token=token)
        hs = HydroShare(auth=auth, hostname=hs_hostname)

        OAuthHS['hs'] = hs
        OAuthHS['token'] = token
        OAuthHS['client_id'] = client_id
        OAuthHS['client_secret'] = client_secret
        OAuthHS['user_name'] = user_name


    except ObjectDoesNotExist as e:
        OAuthHS['error'] = 'ObjectDoesNotExist: ' + e.message
    except TokenExpiredError as e:
        OAuthHS['error'] = 'TokenExpiredError ' + e.message
    except HydroShareNotAuthorized as e:
        OAuthHS['error'] = 'HydroShareNotAuthorized' + e.message
    except HydroShareNotFound as e:
        OAuthHS['error'] = 'HydroShareNotFound' + e.message
    except Exception as e:
        OAuthHS['error'] = 'Authentication Failure:' + e.message

    return OAuthHS

