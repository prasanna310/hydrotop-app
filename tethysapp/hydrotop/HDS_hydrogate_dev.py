__author__ = 'Pabitra'

""""
HydroGate Python Client for accessing CI-WATER HydroDS Data and Computational Web Services
"""
import requests
import os
import json
import pickle
import datetime

class HydroDSException(Exception):
    pass

class HydroDSArgumentException(Exception):
    pass

class HydroDSServerException(Exception):
    pass

class HydroDSBadRequestException(Exception):
    pass

class HydroDSNotAuthorizedException(Exception):
    pass

class HydroDSNotAuthenticatedException(Exception):
    pass

class HydroDSNotFoundException(Exception):
    pass

# TODO: Add HydroGate specific exceptions

def singleton(cls):
    instances = {}

    def getinstance(username=None, password=None):
        if cls not in instances:
            instances[cls] = cls(username, password)
        return instances[cls]
    return getinstance


@singleton
class HydroDS(object):
    def __init__(self, username=None, password=None):
        # print 'HydroDS username: %s, password: %s'%(username,password )
        """
        Create HydroDS object to access client api functions
        :param username: username for HydroDS
        :param password: password for HydroDS
        :return: HydroDS object
        """

        self._hydrogate_base_url = 'https://129.123.9.159/hydrogate'
        self._dataservice_base_url = 'http://129.123.9.159:20199/api/dataservice'
        self._irods_rest_base_url = 'http://hydro-ds.uwrl.usu.edu:8080/irods-rest-4.0.2.1-SNAPSHOT/rest'
        self._hg_token_url = self._hydrogate_base_url + '/request_token/'
        self._hg_upload_pkg_url = self._hydrogate_base_url + '/upload_package/'
        self._hg_upload_pkg_status_url = self._hydrogate_base_url + '/retrieve_package_status'
        self._hg_submit_job_url = self._hydrogate_base_url + '/submit_job/'
        self._hg_job_status_url = self._hydrogate_base_url + '/retrieve_job_status'
        self._hg_token_expire_time_url = self._hydrogate_base_url + '/retrieve_token_expire_time'
        self._hg_hpc_program_names_url = self._hydrogate_base_url + '/return_hpc_program_names/'
        self._hg_program_info_url = self._hydrogate_base_url + '/retrieve_program_info'
        self._requests = requests
        self._hg_auth = (username, password)
        self._hydroshare_auth = None
        self._hg_username = None
        self._hg_password = None
        self._default_hpc = 'USU'
        self._hg_token = None
        self._user_hg_authenticated = False
        self._irods_username = None
        self._irods_password = None
        self._user_irods_authenticated = False

        _ServiceLog.load()

    def check_irods_server_status(self):
        url = '/server'
        response = self._make_irods_rest_call(url)
        if response.status_code != requests.codes.ok:
            raise Exception("iRODS server connection error." + response.reason + " " + response.content)

    def get_irods_collections(self, listing=False):
        url ='/collection//usu/home/rods'
        if listing:
            url += '?listing=true'

        response = self._make_irods_rest_call(url)
        if response.status_code != requests.codes.ok:
            raise Exception("iRODS error:" + response.reason + " " + response.content)

    def _make_irods_rest_call(self, url):
        url = self._irods_rest_base_url + url
        headers = {'content-type': 'application/json'}
        response_format = {'contentType': 'application/json'}
        try:
            response = self._requests.get(url, params=response_format, headers=headers, auth=(self._irods_username,
                                                                                             self._irods_password))
        except Exception as ex:
           raise Exception("iRODS error." + response.reason + " " + response.content)

        return response

    # TODO: Not used
    def login(self, username=None, password=None, hg_username=None, hg_password=None, hpc='USU'):
        self._irods_username = username
        self._irods_password = password
        if hg_username and not hg_password:
            raise Exception("Failed to login. Password for Hydrogate is missing.")

        if not hg_username and hg_password:
            raise Exception("Failed to login. Username for Hydrogate system is missing.")

        if hg_username and hg_password:
            self._hg_token = None
            self._user_hg_authenticated = False
            self._hg_username = hg_username
            self._hg_password = hg_password
            try:
                self._get_token()
                self._user_hg_authenticated = True
            except Exception as ex:
                raise Exception("Failed to login to Hydrogate. " + ex.message)

    def hydrogate_authenticate(self, username, password, hpc='USU'):
        if hpc in self.get_available_hpc():
            self._hg_token = None
            self._user_hg_authenticated = False
            self._hg_username = username
            self._hg_password = password
            try:
                self._requests.auth.HTTPBasicAuth(self._hg_username, self._hg_password)
                self._get_token()
                self._user_hg_authenticated = True
                self._default_hpc = hpc
            except:
                raise HydroDSNotAuthenticatedException("User authentication failed for HPC:{hpc_system}".format(
                    hpc_system=hpc))
        else:
            raise HydroDSNotAuthenticatedException("User authentication for HPC failed. Provided HPC (%s) is not "
                                                   "supported." % hpc)

    def irods_authenticate(self, username, password, hpc=None):
        if hpc:
            if hpc in self.get_available_hpc():
                self._hg_token = None
                self._user_hg_authenticated = False
                self._hg_username = username
                self._hg_password = password
                try:
                    self._requests.auth.HTTPBasicAuth(self._hg_username, self._hg_password)
                    self._get_token()
                    self._user_hg_authenticated = True
                    self._default_hpc = hpc
                except Exception as ex:
                    raise Exception("User authentication for Hydrogate failed." + ex.message)
            else:
                raise Exception("User authentication for Hydrogate failed. Provided HPC system (%s) is not "
                                "supported." % hpc)
        else:
            self._irods_username = username
            self._irods_password = password
            self._user_irods_authenticated = False
            self.check_irods_server_status()
            self._user_irods_authenticated = True

    def get_available_hpc(self):
        return ('USU', 'HydrogateHPC')

    def set_default_hpc(self, hpc):
        available_hpc = self.get_available_hpc()
        if hpc in available_hpc:
            self._default_hpc = hpc
        else:
            raise HydroDSArgumentException("{hpc_system} invalid hpc resource.".format(hpc_system=hpc))

    def get_available_programs(self, hpc=None):
        # returns a list of installed program names that are installed on a specified hpc resource
        self._check_user_hpc_authentication()
        if not self._hg_token:
            self._get_token()
        else:
            if self._get_token_expire_time() == 0:
                self._get_token()

        if not hpc:
            hpc = self._default_hpc

        request_data = {'token': self._hg_token, 'hpc': hpc}
        response = self._requests.post(self._hg_hpc_program_names_url, data=request_data, verify=False)

        if response.status_code != requests.codes.ok:
            raise Exception("HydroGate connection error.")

        response_dict = json.loads(response.content)

        if response_dict['status'] == 'success':
            return response_dict['programnames']
        else:
            raise Exception('Hydrogate error: %s' % response_dict['description'])

    def get_program_info(self, program_name):
        # returns information about specific program/application
        self._check_user_hpc_authentication()
        if not self._hg_token:
            self._get_token()
        else:
            if self._get_token_expire_time() == 0:
                self._get_token()

        request_data = {'token': self._hg_token, 'program': program_name}
        response = self._requests.get(self._hg_program_info_url, params=request_data, verify=False)

        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate connection error.")

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            return response_dict
        else:
            raise Exception('Hydrogate error %s' % response_dict['description'])

    def _get_token(self):
        if self._hg_token:
            return self._hg_token

        user_data = {'username': self._hg_username, 'password': self._hg_password}
        response = self._requests.post(self._hg_token_url, data=user_data, verify=False)
        if response.status_code != requests.codes.ok:
            raise Exception("HydroGate connection error.")

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            self._hg_token = response_dict['token']
            return self._hg_token
        else:
            raise Exception('Hydrogate error:%s' % response_dict['description'])

    def _get_token_expire_time(self):
        # returns token expire time in seconds (0 means token has expired)
        self._check_user_hpc_authentication()
        if not self._hg_token:
            return 0

        request_data = {'token': self._hg_token}
        response = self._requests.get(self._hg_token_expire_time_url, params=request_data, verify=False)

        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate connection error.")

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            return response_dict['remainingexpiretime']
        else:
            raise Exception('Hydrogate error: %s' % response_dict['description'])

    def show_service_request_history(self, order='first', count=None):
        _ServiceLog.print_log(order=order, count=count)

    def get_most_recent_request(self, service_name=None, service_id_name=None, service_id_value=None):
        return _ServiceLog.get_most_recent_request(service_name, service_id_name, service_id_value)

    def upload_package(self, package_file_url_path):
        self._check_user_hpc_authentication()

        if not self._hg_token:
            self._get_token()
        else:
            if self._get_token_expire_time() == 0:
                self._get_token()

        # location of the file to be uploaded (must be a url file path).
        request_data = {'token': self._hg_token, 'package': package_file_url_path, 'hpc': self._default_hpc}
        response = self._requests.post(self._hg_upload_pkg_url, data=request_data, verify=False)

        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate connection error.")

        response_dict = json.loads(response.content)

        if response_dict['status'] == 'success':
            package_id = response_dict['packageid']
            service_req = ServiceRequest(service_name='upload_package', service_id_name='packageID',
                                         service_id_value=package_id, service_status='success')
            _ServiceLog.add(service_req)
            self.save_service_call_history()
            return service_req
        else:
            raise Exception('Hydrogate error: package uploading failed:%s' % response_dict['description'])

    def get_upload_status(self, package_id=None):
        if not package_id:
            # TODO: get the most recent service request object that has a package id
            last_request = _ServiceLog.get_most_recent_request(service_id_name='packageID')
            if not last_request:
                return None
            else:
                package_id = last_request.service_id_value

        if not self._hg_token:
            self._get_token()
        else:
            if self._get_token_expire_time() == 0:
                self._get_token()

        request_data = {'token': self._hg_token, 'packageid': int(package_id)}
        response = self._requests.get(self._hg_upload_pkg_status_url, params=request_data, verify=False)
        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate error." + response.reason + " " + response.content)

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            upload_status = response_dict['state']
            service_req = ServiceRequest(service_name='retrieve_package_upload_status', service_id_name='packageID',
                                         service_id_value=package_id, service_status=upload_status)
            _ServiceLog.add(service_req)
            self.save_service_call_history()
            return service_req
        else:
            raise Exception('Hydrogate error:' + response_dict['description'])

    def submit_job(self, package_id, program_name, input_raster_file_name=None, **kwargs):
       # TODO: check that the user provided program_name is one of the supported programs using the get_available_programs()
        self._check_user_hpc_authentication()

        if self._get_token_expire_time() == 0:
            self._get_token()

        job_def = {}
        if len(kwargs) > 0:
            job_def = kwargs
        else:
            if program_name == 'pitremove':
                if input_raster_file_name is None:
                    raise Exception("A value for paramter input_raster_file_name is needed for running pitremove")
                job_def['program'] = 'pitremove'
                job_def['walltime'] = '00:00:50'
                job_def['outputlist'] = ['fel*.tif']
                job_def['parameters'] = {'z': input_raster_file_name, 'fel': 'feloutput.tif'}
            elif program_name == 'uebpar':
                job_def['program'] = 'uebpar'
                job_def['walltime'] = '00:59:50'
                job_def['outputlist'] = ['SWE.nc', 'aggout.nc', 'SWIT.nc', 'SWISM.nc']
                #job_def['parameters'] = {'wdir': './'}
                #job_def['runner_param'] = "-wdir .hydrogate/data/ea132802-24fe-11e5-9d14-0050569b33c6/JOB_91/LiitleBear1000"
                job_def['parameters'] = {'wdir': './' , 'control': 'control.dat'}
            else:
                raise Exception("Program parameters are missing for '%s'." % program_name)

        request_data = {'token': self._hg_token, 'packageid': int(package_id), 'jobdefinition': json.dumps(job_def)}
        response = self._requests.post(self._hg_submit_job_url, data=request_data, verify=False)
        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate connection error.")

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            job_id = response_dict['jobid']
            output_file_path = response_dict['outputpath']
            service_req = ServiceRequest(service_name='submit_job', service_id_name='jobID',
                                         service_id_value=job_id, service_status='success', file_path=output_file_path)
            _ServiceLog.add(service_req)
            self.save_service_call_history()
            return service_req
        else:
            raise Exception('Hydrogate error:%s' % response_dict['description'])

    def get_job_status(self, job_id):
        self._check_user_hpc_authentication()

        if self._get_token_expire_time() == 0:
            self._get_token()

        request_data = {'token': self._hg_token, 'jobid': job_id}
        response = self._requests.get(self._hg_job_status_url, params=request_data, verify=False)
        if response.status_code != requests.codes.ok:
            raise Exception("Hydrogate error." + response.reason + " " + response.content)

        response_dict = json.loads(response.content)
        if response_dict['status'] == 'success':
            job_status = response_dict['state']
            service_req = ServiceRequest(service_name='retrieve_job_status', service_id_name='jobID',
                                         service_id_value=job_id, service_status=job_status)
            _ServiceLog.add(service_req)
            self.save_service_call_history()
            return job_status
        else:
            raise Exception('Hydrogate error:%s' % response_dict['description'])

    def list_my_files(self):
        """
        Lists url file paths for all the files the user owns on HydroDS api server

        :return: a list of url file paths

        :raises: HydroDSNotAuthenticatedException: provided user account failed validation

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.list_my_file()
            # print url file path all the files user owns
            for file_url in response_data:
                print(file_url)
        """

        url = self._get_dataservice_specific_url('myfiles/list')
        response = self._make_data_service_request(url=url)
        return self._process_dataservice_response(response, save_as=None)

    def delete_my_file(self, file_name):
        """
        Deletes a user file

        :param file_name: name of the file (user owned) to be deleted from the HydroDS api server
        :type file_name: string
        :return: name of the file that got deleted

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified file to be deleted does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.delete_my_file(file_name=logan.tif)

            # print name of the file that got deleted
            print(hds_response_data)
        """
        if not self._is_file_name_valid(file_name):
            raise HydroDSArgumentException("{file_name} is not a valid file name".format(file_name=file_name))

        url = self._get_dataservice_specific_url('myfiles/delete/{file_name}'.format(file_name=file_name))
        response = self._make_data_service_request(url=url, http_method='DELETE')
        return self._process_dataservice_response(response, save_as=None)

    def get_static_files_info(self):
        """
        Gets a list of supported data resources on the HydroDS api server

        :return: a list of supported data files including metadata for each file

        example of return data:
        [
            {
                "variables": [
                    {
                        "name": "DEM",
                        "description": "Digital Elevation Model",
                        "unit": "N/A"
                    }
                ],
                "time_period": "N/A",
                "spatial_extent": "Western USA",
                "data_source": "USGS",
                "data_format": "Tiff",
                "file_name": "nedWesternUS.tif"
            },
            {
                "variables": [
                    {
                        "name": "NLCD",
                        "description": "National Land Cover Dataset",
                        "unit": "N/A"
                    }
                ],
                "time_period": "N/A",
                "spatial_extent": "Whole USA",
                "data_source": "USGS",
                "data_format": "Tiff",
                "file_name": "nlcd2011CONUS.tif"
            }
        ]
        """

        url = self._get_dataservice_specific_url('showstaticdata/info')
        response = self._make_data_service_request(url=url)
        return self._process_dataservice_response(response, save_as=None)

    def subset_raster(self, left, top, right, bottom, input_raster, output_raster, save_as=None):
        """
        Subset raster data

        :param left: x-coordinate of the left-top corner of the bounding box
        :type left: float
        :param top: y-coordinate of the left-top corner of the bounding box
        :type top: float
        :param right: x-coordinate of the right-bottom corner of the bounding box
        :type right: float
        :param bottom: y-coordinate of the right-bottom corner of the bounding box
        :type bottom: float
        :param input_raster: raster file to subset from (this can either be a url path for the user file on the HydroDS
                             server or name of a relevant supported data file on the HydroDS server)
        :param output_raster: name for the output (subsetted) raster file (if there is file already with the same name
                              it will be overwritten)
        :type output_raster: string
        :param save_as: (optional) file name and file path to save the subsetted raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the generated raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.subset_raster(left=-111.97, top=42.11, right=-111.35, bottom=41.66,
                                              input_raster='nedWesternUS.tif', output_raster='subset_dem_logan.tif')

            output_subset_dem_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_subset_dem_url)
        """

        url = self._get_dataservice_specific_url(service_name='rastersubset') ##
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        self._validate_boundary_box(bottom, left, right, top)

        payload = {'xmin': left, 'ymin': bottom, 'xmax': right, 'ymax': top, 'input_raster': input_raster,
                   'output_raster': output_raster}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    # TODO: this one not working as the HydroDS service api is not working
    def subset_usgs_ned_dem(self, left, top, right, bottom, output_raster, save_as=None):
        """
        Subsets usgs ned dem and creates a new tif file with the subset data

        :param left: x-coordinate of the left-top corner of the bounding box
        :param top: y-coordinate of the left-top corner of the bounding box
        :param right: x-coordinate of the right-bottom corner of the bounding box
        :param bottom: y-coordinate of the right-bottom corner of the bounding box
        :param output_raster: name of for the output raster
        :param save_as: (optional) subset dem tif file to save as (file name with path)
        :return: a dictionary with key 'output_raster' and value of url path for the combined raster file

        """
        url = self._get_dataservice_specific_url(service_name='subsetUSGSNEDDEM')
        if save_as:
            self._validate_file_save_as(save_as)

        self._validate_boundary_box(bottom, left, right, top)
        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_raster))

        payload = {'xmin': left, 'ymin': bottom, 'xmax': right, 'ymax': top, 'output_raster': output_raster}
        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def subset_raster_to_reference(self, input_raster_url_path, ref_raster_url_path, output_raster, save_as=None):
        """
        Subset raster data based on a reference raster data

        :param input_raster_url_path: url file path for the user owned raster file (on the HydroDS server)
                                      to subset from
        :type input_raster_url_path: string
        :param ref_raster_url_path: url file path for the user owned raster file (on the HydroDS server) to be used as
                                    a reference for subsetting
        :param output_raster: name for the output (subsetted) raster file (if there is file already with the same name
                              it will be overwritten)
        :param save_as: (optional) raster file name and file path to save the projected/resampled raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the subset raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.subset_raster_to_reference(input_raster_url_path=your_input_raster_url_here,
                                                           ref_raster_url_path=your_ref_input_raster_url_here,
                                                           output_raster='subset_to_spawn.tif')
            output_subset_raster_url = response_data['output_raster']

            # print the url path for the generated netcdf file
            print(output_subset_raster_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        url = self._get_dataservice_specific_url('subsetrastertoreference')
        payload = {"input_raster": input_raster_url_path, 'reference_raster': ref_raster_url_path,
                   'output_raster': output_raster}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def raster_to_netcdf_and_rename_variable(self, input_raster_url_path, output_netcdf, increasing_x=False,
                                             increasing_y=False, output_varname='Band1', save_as=None):
        """
        Generate a netcdf file from a raster file (convert data in raster format to netcdf format)
        Additionally reorder netcdf data in the direction of increasing X-coordinate and/or increasing Y-coordinate
        values

        :param input_raster_url_path: url file path for the (user owned) raster on HydroDS api server to be used for
                                      generating a netcdf file
        :type input_raster_url_path: string
        :param output_netcdf: name for the generated netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param increasing_x: (optional) if data in netcdf format to be ordered in the direction of increasing
                             X-coordinate (default is False)
        :type increasing_x: bool
        :param increasing_y: (optional) if data in netcdf format to be ordered in the direction of increasing
                             Y-coordinate (default is False)
        :type increasing_y: bool
        :param output_varname: name for the output NetCDF data variable
        :type output_varname: string
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the generated netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.raster_to_netcdf_and_rename_variable(input_raster_url_path=provide_input_raster_url_path_here,
                                                 increasing_x=False, increasing_y=True,
                                                 output_netcdf='raster_to_netcdf_slope_logan.nc')

            output_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException('{file_name} is not a valid NetCDF file '
                                           'name.'.format(file_name=output_netcdf))

        if not isinstance(increasing_x, bool):
            raise HydroDSArgumentException("increasing_x must be a boolean value")

        if not isinstance(increasing_y, bool):
            raise HydroDSArgumentException("increasing_y must be a boolean value")

        url = self._get_dataservice_specific_url('rastertonetcdfrenamevariable')
        payload = {"input_raster": input_raster_url_path, 'output_netcdf': output_netcdf, 'increasing_x': increasing_x,
                   'increasing_y': increasing_y, 'output_varname': output_varname}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def raster_to_netcdf(self, input_raster_url_path, output_netcdf, save_as=None):
        """
        Generate a netcdf file from a raster file (convert data in raster format to netcdf format)

        :param input_raster_url_path: url file path for the (user owned) raster on HydroDS api server to be used for
                                      generating a netcdf file
        :type input_raster_url_path: string
        :param output_netcdf: name for the generated netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the generated netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.raster_to_netcdf(input_raster_url_path=provide_input_raster_url_path_here,
                                                 output_netcdf='raster_to_netcdf_slope_logan.nc')

            output_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException('{file_name} is not a valid NetCDF file '
                                           'name.'.format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('rastertonetcdf')
        payload = {"input_raster": input_raster_url_path, 'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def create_raster_slope(self, input_raster_url_path, output_raster, save_as=None):
        """
        Creates a raster with slope data

        :param input_raster_url_path: url file path of the raster file (user owned) on HydroDS api server for which
                                      slope data is needed
        :type input_raster_url_path: string
        :param output_raster: name of the output slope raster file (if there is file already with the same name it
                              will be overwritten)
        :type output_raster: string
        :param save_as: (optional) raster file name and file path to save the generated slope raster file locally
        :type save_as: string
        :return:a dictionary with key 'output_raster' and value of url path for the slope raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.create_raster_slope(input_raster_url_path=raster_url,
                                                        output_raster='slope_raster.tif',
                                                        save_as=r'C:\hydro-ds\slope_raster.tif')

            # print url path of the slope raster file
            output_slope_raster_url = hds_response_data['output_raster']
            print(output_slope_raster_url)
        """
        return self._create_raster_slope_or_aspect('computerasterslope', input_raster_url_path, output_raster, save_as)

    def create_raster_aspect(self, input_raster_url_path, output_raster, save_as=None):
        """
        Creates a raster with aspect data

        :param input_raster_url_path: url file path of the raster file (user owned) on HydroDS api server for which
                                      aspect data is needed
        :type input_raster_url_path: string
        :param output_raster: name of the output aspect raster file (if there is file already with the same name it
                              will be overwritten)
        :type output_raster: string
        :param save_as: (optional) raster file name and file path to save the generated aspect raster file locally
        :type save_as: string
        :return:a dictionary with key 'output_raster' and value of url path for the aspect raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.create_raster_aspect(input_raster_url_path=raster_url,
                                                        output_raster='aspect_raster.tif',
                                                        save_as=r'C:\hydro-ds\aspect_raster.tif')

            # print url path of the aspect raster file
            output_aspect_raster_url = hds_response_data['output_raster']
            print(output_aspect_raster_url)
        """

        return self._create_raster_slope_or_aspect('computerasteraspect', input_raster_url_path, output_raster, save_as)

    def _create_raster_slope_or_aspect(self, service_name,  input_raster_url_path, output_raster, save_as=None):
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url(service_name)
        payload = {"input_raster": input_raster_url_path}
        if not self._is_file_name_valid(output_raster, ext='.tif'):
            err_msg = "Invalid output raster file name:{file_name}".format(file_name=output_raster)
            raise HydroDSArgumentException(err_msg)

        payload['output_raster'] = output_raster

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_clip_raster(self, input_raster, ref_raster_url_path, output_raster, save_as=None):
        """
        Project and clip a raster based on a reference raster

        :param input_raster: raster to be projected and clipped (just the file name if this data is supported by
                             HydroDS otherwise, HydroDS url file path)
        :type input_raster: string
        :param ref_raster_url_path: url path of the raster (user owned) to be used as the reference for projection and
                                    clipping
        :type ref_raster_url_path: string
        :param output_raster: name for the output raster (if there is file already with the same name it will be
                              overwritten)
        :type output_raster: string
        :param save_as: (optional) file name and file path to save the generated raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the generated raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            input_raster = 'nlcd2011CONUS.tif'  # this a supported data resource file on the HydroDS api server
            hds_response_data =  hds.project_clip_raster(input_raster=input_raster,
                                                         ref_raster_url_path=provide_ref_input_raster_url_path_here,
                                                         output_raster='nlcd_proj_spwan.tif')

            # print url path of the projected/clipped raster file
            output_raster_url = hds_response_data['output_raster']
            print(output_raster_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('projectandcliprastertoreference')
        payload = {"input_raster": input_raster, 'reference_raster': ref_raster_url_path}
        self._is_file_name_valid(output_raster, ext='.tif')
        payload['output_raster'] = output_raster

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def get_canopy_variable(self, input_NLCD_raster_url_path, variable_name, output_netcdf, save_as=None):
        """
        Generates a netcdf file that contains NLCD data for a given variable

        :param input_NLCD_raster_url_path: url file path for the raster (user owned) on the HydroDS api server for
                                           which NLCD data needs to be generated
        :type input_NLCD_raster_url_path: string
        :param variable_name: name of the data variable (valid variable names are: 'cc', 'hcan', 'lai')
        :type variable_name: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the netcdf file generated

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.get_canopy_variable(input_NLCD_raster_url_path=provide_input_NLCD_raster_url_path_here,
                                                        variable_name='cc', output_netcdf='nlcd_cc_spwan.nc',
                                                        save_as=r'C:\hydro-DS_test\nlcd_cc_spwan.nc')

            # print the url path for the generated netcdf file containing canopy variable data
            output_canopy_netcdf_url = hds_response_data['output_netcdf']
            print(output_canopy_netcdf_url)

        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('getcanopyvariable')
        payload = {"in_NLCDraster": input_NLCD_raster_url_path, 'variable_name': variable_name,
                   'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as=save_as)

    # TODO: We should not support the following method. The functionality of this mkethod can be achieved by calling
    # 3 time the get_canopy_variable() method
    def get_canopy_variables(self, input_NLCD_raster_url_path, output_ccNetCDF=None, output_hcanNetCDF=None,
                             output_laiNetCDF=None):

        url = self._get_dataservice_specific_url('getcanopyvariables')
        payload = {"in_NLCDraster": input_NLCD_raster_url_path}
        if output_ccNetCDF:
            if not self._is_file_name_valid(output_ccNetCDF, ext='.nc'):
                raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(
                    file_name=output_ccNetCDF))
            payload['out_ccNetCDF'] = output_ccNetCDF

        if output_hcanNetCDF:
            if not self._is_file_name_valid(output_hcanNetCDF, ext='.nc'):
                raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(
                    file_name=output_hcanNetCDF))
            payload['out_hcanNetCDF'] = output_hcanNetCDF

        if output_laiNetCDF:
            if not self._is_file_name_valid(output_laiNetCDF, ext='.nc'):
                raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(
                    file_name=output_laiNetCDF))
            payload['out_laiNetCDF'] = output_laiNetCDF

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as=None)

    def combine_rasters(self, input_one_raster_url_path, input_two_raster_url_path, output_raster, save_as=None):
        """
        Combines two rasters to create a new raster

        :param input_one_raster_url_path: url file path for the 1st raster file (user owned) on HydroDS api server
        :type input_one_raster_url_path: string
        :param input_two_raster_url_path: url file path for the 2nd raster file (user owned) on HydroDS api server
        :type input_two_raster_url_path: string
        :param output_raster: name of the output (combined) raster file (if there is file already with the same name it
                              will be overwritten)
        :type output_raster: string
        :param save_as: (optional) raster file name and file path to save the generated combined raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the combined raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.combine_rasters(input_one_raster_url_path=provide_raster_one_url_here,
                                                    input_two_raster_url_path=provide_raster_two_url_here,
                                                    output_raster='combined_rasters.tif',
                                                    save_as=r'C:\hydro-ds\combined_raster.tif')

            # print url path of the combined raster file
            output_combined_raster_url = hds_response_data['output_raster']
            print(output_combined_raster_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        url = self._get_dataservice_specific_url('combinerasters')
        payload = {"input_raster1": input_one_raster_url_path, "input_raster2": input_two_raster_url_path,
                   'output_raster': output_raster}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    # TODO: Not working - no HydroDS web service
    def get_daymet_mosaic(self, start_year, end_year, save_as=None):
        if save_as:
            if not self._validate_file_save_as(save_as):
                return

        # TODO: check with Tseganeh for the valid year range (1980 -2013)
        try:
            int(start_year)
        except:
            raise Exception("Error:Invalid start year. Year must be an integer value.")

        try:
            int(end_year)
        except:
            raise Exception("Error:Invalid end year. Year must be an integer value.")

        url = self._dataservice_base_url + '/downloaddaymetmosaic'

        if end_year > start_year:
            payload = {"startyear": start_year, "endyear": end_year}
        else:
            payload = {"startyear": end_year, "endyear": start_year}

        response = self._requests.get(url, params=payload)
        return self._process_service_response(response, "get_daymet_mosaic", save_as)

    # TODO: Not working - no HydrDS web service
    def get_daymet_tile(self, start_year, end_year, start_tile, end_tile, save_as=None):
        if save_as:
            # TODO: should we check that the file extension must be  .tif type for saving
            if not self._validate_file_save_as(save_as):
                return

        # TODO: check with Tseganeh for the valid year range
        try:
            int(start_year)
        except:
            raise Exception("Error:Invalid start year. Year must be an integer value.")

        try:
            int(end_year)
        except:
            raise Exception("Error:Invalid end year. Year must be an integer value.")

        try:
            int(start_tile)
        except:
            raise Exception("Error:Invalid start tile number. Tile number must be an integer value.")

        try:
            int(end_tile)
        except:
            raise Exception("Error:Invalid end tile number. Tile number must be an integer value.")

        url = self._dataservice_base_url + '/downloaddaymettile'

        if end_year > start_year:
            payload = {"startyear": start_year, "endyear": end_year}
        else:
            payload = {"startyear": end_year, "endyear": start_year}

        payload["starttile"] = start_tile
        payload["endtile"] = end_tile
        response = self._requests.get(url, params=payload)
        return self._process_service_response(response, "get_daymet_tile", save_as)

    def reverse_netcdf_yaxis(self, input_netcdf_url_path, output_netcdf, save_as=None):
        """
        Reverse netcdf Y-coordinate data

        :param input_netcdf_url_path: url file path of a netcdf file (user owned) on HydroDS api server for which data
                                      needs to be reversed
        :type input_netcdf_url_path: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :return: a dictionary with key 'output_netcdf' and value of url path for the output netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file doesn't exist on HydroDS server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.reverse_netcdf_yaxis(input_netcdf_url_path=provide_input_netcdf_url_here,
                                                     output_netcdf='resample_reverse_yaxis.nc')

            output_reverse_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_reverse_netcdf_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('reversenetcdfyaxis')
        payload = {"input_netcdf": input_netcdf_url_path, 'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def reverse_netcdf_yaxis_rename_variable(self, input_netcdf_url_path, output_netcdf, input_variable_name=None,
                                             output_variable_name=None, save_as=None):
        """
        Reverse netcdf data in the direction of Y-coordinate and optionally rename variable

        :param input_netcdf_url_path: url file path for a netcdf file (user owned) on the HydroDS api server for which
                                      data to be reversed and variable to be renamed
        :type input_netcdf_url_path: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param input_variable_name: (optional) name of the variable in the input netcdf file
        :type input_variable_name: string
        :param output_variable_name: (optional) new name for the variable
        :type output_variable_name: string
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the output netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file doesn't exist on HydroDS server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.reverse_netcdf_yaxis_rename_variable(input_netcdf_url_path=provide_input_netcdf_url_here,
                                                             input_variable_name='Band1', output_variable_name='Band1',
                                                             output_netcdf='resample_reverse_yaxis_rename_variable.nc')

            output_reverse_rename_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_reverse_rename_netcdf_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('reversenetcdfyaxisandrenamevariable')
        payload = {"input_netcdf": input_netcdf_url_path}
        if input_variable_name:
            payload['input_varname'] = input_variable_name

        if output_variable_name:
            payload['output_varname'] = output_variable_name

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file name".format(file_name=output_netcdf))

        payload['output_netcdf'] = output_netcdf

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def netcdf_rename_variable(self, input_netcdf_url_path, output_netcdf, input_variable_name=None,
                               output_variable_name=None, save_as=None):
        """
        Rename netcdf variable

        :param input_netcdf_url_path: url file path for a netcdf file (user owned) on the HydroDS api server for which
                                      variable to be renamed
        :type input_netcdf_url_path: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param input_variable_name: (optional) name of the variable in the input netcdf file
        :type input_variable_name: string
        :param output_variable_name: (optional) new name for the variable
        :type output_variable_name: string
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the output netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file doesn't exist on HydroDS server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.netcdf_rename_variable(input_netcdf_url_path=provide_input_netcdf_url_here,
                                                       input_variable_name='Band1', output_variable_name='Band1',
                                                       output_netcdf='rename_variable.nc')

            output_rename_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_rename_netcdf_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('netcdfrenamevariable')
        payload = {"input_netcdf": input_netcdf_url_path}
        if input_variable_name:
            payload['input_varname'] = input_variable_name

        if output_variable_name:
            payload['output_varname'] = output_variable_name

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file name".format(file_name=output_netcdf))

        payload['output_netcdf'] = output_netcdf

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def subset_netcdf(self, input_netcdf, ref_raster_url_path, output_netcdf, save_as=None):
        """
        Subset netcdf data based on a reference raster

        :param input_netcdf: either a file name for a supported netcdf data resource (static data file) on HydroDS api server
                             or url file path for a netcd file that the user owns on the HydroDS server
        :type input_netcdf: string
        :param ref_raster_url_path: url file path for a raster file (user owned) on the HydroDS api server that needs
                                    to be used as a reference for subsetting
        :type ref_raster_url_path: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the output netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file doesn't exist on HydroDS server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.subset_netcdf(input_netcdf=provide_input_netcdf_static_file_name_or_url_file_path_here,
                                              ref_raster_url_path=ref_input_raster_url,
                                              output_netcdf='subset_netcdf_to_spawn.nc')

            output_subset_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_subset_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('subsetnetcdftoreference')
        payload = {"input_netcdf": input_netcdf, 'reference_raster': ref_raster_url_path,
                   'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def subset_netcdf_by_time(self, input_netcdf_url_path, time_dimension_name, start_date, end_date,
                              output_netcdf, save_as=None):
        """
        Subset a netcdf file by time dimension

        :param input_netcdf_url_path: url file path for the user owned netcdf file to be subsetted
        :type input_netcdf_url_path: string
        :param time_dimension_name: name of time dimension variable in the input netcdf file
        :type time_dimension_name: string
        :param start_date: data start date for subsetting
        :type start_date: string (must be of format: 'mm/dd/yyyy')
        :param end_date: date end date for subsetting
        :type end_date: string (must be of format: 'mm/dd/yyyy')
        :param output_netcdf: name for the output (subsetted) netcdf file (if there is file already with the same name
                              it will be overwritten)
        :type output_netcdf: string
        :param save_as: (optional) netcdf file name and file path to save the subsetted netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the generated netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.subset_netcdf_by_time(input_netcdf_url_path=provide_input_netcdf_url_path_here,
                                                      time_dimension_name='time', start_date='01/01/2010',
                                                      end_date='01/11/2010',
                                                      output_netcdf='subset_prcp_spwan_1_to_10_days.nc')

            output_subset_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_subset_netcdf_url)
        """
        DATE_FORMAT = "%m/%d/%Y"
        if save_as:
            self._validate_file_save_as(save_as)

        try:
            start_date_value = datetime.datetime.strptime(start_date, DATE_FORMAT)
        except ValueError:
            raise HydroDSArgumentException("start_date must be a string in the format of 'mm/dd/yyyy'")

        try:
            end_date_value = datetime.datetime.strptime(end_date, DATE_FORMAT)
        except ValueError:
            raise HydroDSArgumentException("end_date must be a string in the format of 'mm/dd/yyyy'")

        if start_date_value > end_date_value:
            raise HydroDSArgumentException("start_date must be a date before the end_date")

        start_time_index = start_date_value.day
        end_time_index = start_date_value.day + (end_date_value - start_date_value).days

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException('{file_name} is not a valid NetCDF file '
                                           'name.'.format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('subsetnetcdfbytime')
        payload = {"input_netcdf": input_netcdf_url_path, 'time_dim_name': time_dimension_name,
                   'start_time_index': start_time_index, 'end_time_index': end_time_index,
                   'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_netcdf(self, input_netcdf_url_path, utm_zone, variable_name, output_netcdf, save_as=None):
        """
        Projects a netcdf file

        :param input_netcdf_url_path: url file path for the netcdf file (user owned) on the HydroDS api server to be
                                      projected
        :param utm_zone: UTM zone value to use for projection
        :type utm_zone: integer
        :param variable_name: name of the data variable for which data to be projected
        :type variable_name: string
        :param output_netcdf: name for the output (projected) netcdf file (if there is file already with the same name
                              it will be overwritten)
        :type output_netcdf: string
        :param save_as: (optional) file name and file path to save the projected netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the projected netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.project_netcdf(input_netcdf_url_path=provide_input_netcdf_url_path_here,
                                                   variable_name='prcp', utm_zone=12,
                                                   output_netcdf='projected_prcp_spwan.nc')

            # print the url path for the projected netcdf file
            output_projected_netcdf_url = hds_response_data['output_netcdf']
            print(output_projected_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)
        try:
            int(utm_zone)
        except TypeError:
            raise HydroDSArgumentException("A value for utm_zone must be an integer number")

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException('{file_name} is not a valid NetCDF file '
                                           'name.'.format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('projectnetcdf')
        payload = {"input_netcdf": input_netcdf_url_path, 'variable_name': variable_name, 'utm_zone': utm_zone,
                   'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_subset_resample_netcdf(self, input_netcdf_url_path, ref_netcdf_url_path, variable_name,
                                       output_netcdf, save_as=None):
        """
        Project, subset, and resample a netcdf file

        :param input_netcdf_url_path: url file path for the user owned netcdf file to be projected, subsetted,
                                      and resampled
        :type input_netcdf_url_path: string
        :param ref_netcdf_url_path: url file path for the user owned netcdf file to be used as the reference
        :type ref_netcdf_url_path: string
        :param variable_name:  name of the data variable in input netcdf to be used for projection and resampling
        :type variable_name: string
        :param output_netcdf: name for the output (projected/subsetted/resampled) netcdf file (if there is file already
                              with the same name it will be overwritten)
        :type output_netcdf: string
        :param save_as: (optional) netcdf file name and file path to save the projected/subsetted/resampled netcdf file
                        locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the generated netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.project_subset_resample_netcdf(input_netcdf_url_path=provide_input_netcdf_url_path_here,
                                                               ref_netcdf_url_path=provide_ref_netcdf_url_path_here,
                                                               variable_name='prcp',
                                                               output_netcdf='proj_subset_resample_prcp_spwan.nc')
            output_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException('{file_name} is not a valid NetCDF file '
                                           'name.'.format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('projectsubsetresamplenetcdftoreferencenetcdf')
        payload = {"input_netcdf": input_netcdf_url_path, 'reference_netcdf': ref_netcdf_url_path,
                   'variable_name': variable_name, 'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def concatenate_netcdf(self, input_netcdf1_url_path, input_netcdf2_url_path, output_netcdf, save_as=None):
        """
        Joins two netcdf files to create a new netcdf file

        :param input_netcdf1_url_path: url file path for the 1st netcdf file (user owned) on HydroDS api server
        :type input_netcdf1_url_path: string
        :param input_netcdf2_url_path: url file path for the 2nd netcdf file (user owned) on HydroDS api server
        :type input_netcdf2_url_path: string
        :param output_netcdf: name of the output (concatenated) netcdf file (if there is file already with the same name
                              it will be overwritten)
        :type output_netcdf: string
        :param save_as: (optional) file name and file path to save the generated concatenated netcdf file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the joined netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.concatenate_netcdf(input_netcdf1_url_path=provide_url_path_for_1st_netcdf_file,
                                                       input_netcdf2_url_path=provide_url_path_for_2nd_netcdf_file,
                                                       output_netcdf='concatenated.nc',
                                                       save_as=r'C:\hydro-DS_test\concatenated_prcp_2015.nc')

            # print the url path for the concatenated netcdf file
            output_concatenated_netcdf_url = hds_response_data['output_netcdf']
            print(output_concatenated_netcdf_url)

        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('concatenatenetcdf')
        payload = {"input_netcdf1": input_netcdf1_url_path, "input_netcdf2": input_netcdf2_url_path,
                   'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_raster_to_UTM_NAD83(self, input_raster_url_path, utm_zone, output_raster, save_as=None):
        """
        Project a raster to UTM NAD83 projection

        :param input_raster_url_path: url file path for the (user owned) raster on the HydroDS api server to be
                                      projected
        :type input_raster_url_path: string
        :param utm_zone: UTM zone value to be used for projection
        :type utm_zone: integer
        :param output_raster: name for the output (projected) raster file (if there is file already with the same name
                              it will be overwritten)
        :type output_raster: string
        :param save_as: (optional) raster file name and file path to save the projected raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the projected raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.project_raster_to_UTM_NAD83(input_raster_url_path=provide_raster_file_url_path_here,
                                                                utm_zone=12, output_raster='projected_raster.tif')

            # print url path of the projected raster file
            output_projected_raster_url = hds_response_data['output_raster']
            print(output_projected_raster_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))
        try:
            int(utm_zone)
        except TypeError:
            raise HydroDSArgumentException("A value for utm_zone must be an integer number")

        url = self._get_dataservice_specific_url('projectraster')
        payload = {"input_raster": input_raster_url_path, 'utmZone': utm_zone, 'output_raster': output_raster}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_shapefile(self, input_shapefile_url_path, output_shape_file, utm_zone=None, epsg_code=None,
                          save_as=None):

        """
        Project a shapefile either based on UTM zone or EPSG code

        :param input_shapefile_url_path: url file path for the (user owned) shapefile on the HydroDS api server to be
                                         projected
        :type input_shapefile_url_path: string
        :param output_shape_file: name for the output (projected) shapefile (file type must be '.shp'). Generated
                                  shapefile is saved on the HydroDS server as a zip file. (if there is file already
                                  with the same name it will be overwritten)
        :type output_shape_file: string
        :param utm_zone: UTM zone value to be used for projection (required if epsg_code is None)
        :type utm_zone: integer
        :param epsg_code: EPSG code value to be used for projection (required if utm_zone is None)
        :type epsg_code: integer
        :param save_as: (optional) shapefile name and file path to save the projected shapefile locally
        :type save_as: string
        :return: a dictionary with key 'output_shape_file' and value of url path for the projected shapefile file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)

            # projection using UTM zone
            response_data = hds.project_shapefile(input_shapefile_url_path=provide_input_shapefile_url_path_here,
                                                  utm_zone=12, output_shape_file='outlet-proj_utm.shp')
            output_proj_utm_shapefile_url = response_data['output_shape_file']

            # print the url path for the generated shapefile
            print(output_proj_utm_shapefile_url)

            # projection using EPSG code
            response_data = hds.project_shapefile(input_shapefile_url_path=your_input_shapefile_url, epsg_code=2152,
                                                  output_shape_file='outlet-proj_epsg.shp')

            output_proj_epsg_shapefile_url = response_data['output_shape_file']

            # print the url path for the generated shapefile
            print(output_proj_epsg_shapefile_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if utm_zone is None and epsg_code is None:
            raise HydroDSArgumentException("A value for either utm_zone or epsg_code is required")

        if utm_zone and epsg_code:
            raise HydroDSArgumentException("A value for either utm_zone or epsg_code is needed and not both")

        if not self._is_file_name_valid(output_shape_file, ext='.shp'):
            raise HydroDSArgumentException('{file_name} is not a valid shapefile '
                                           'name.'.format(file_name=output_shape_file))

        payload = {"input_shape_file": input_shapefile_url_path, 'output_shape_file': output_shape_file}
        url = None
        if utm_zone:
            if not isinstance(utm_zone, int):
                raise HydroDSArgumentException("utm_zone value must be an integer")
            payload['utm_zone'] = utm_zone
            url = self._get_dataservice_specific_url('projectshapefileutm')

        if epsg_code:
            if not isinstance(epsg_code, int):
                raise HydroDSArgumentException("epsg_code value must be an integer")
            payload['epsg_code'] = epsg_code
            url = self._get_dataservice_specific_url('projectshapefileepsg')

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def create_outlet_shapefile(self, point_x, point_y, output_shape_file_name, save_as=None):
        """
        Create an outlet shapefile. The generated shapefile is stored on the server as a zip file

        :param point_x: X-coordinate of outlet point
        :type point_x: float
        :param point_y: Y-coordinate of outlet point
        :type point_y: float
        :param output_shape_file_name: name of the outlet shapefile (must be of type .shp)(if there is file already
                                       with the same name it will be overwritten)
        :type output_shape_file_name: string
        :param save_as: (optional) shapefile name and file path to save the generated shapefile locally
        :type save_as: string
        :return: a dictionary with key 'output_shape_file' and value of url path for the outlet shapefile

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds_response_data = hds.create_outlet_shapefile(point_x=-111.787, point_y=41.742,
                                                            output_shape_file='outlet-shape.shp'
                                                            save_as=r'C:\hydro-DS_test\outlet.zip')

            # print the url path for the outlet shapefile
            output_outlet_shape_file_url = hds_response_data['output_shape_file_name']
            print(output_outlet_shape_file_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url(service_name='createoutletshapefile')
        payload = {"outletPointX": point_x, 'outletPointY': point_y}
        if not self._is_file_name_valid(output_shape_file_name, ext='.shp'):
            raise HydroDSArgumentException('{file_name} is not a valid shapefile '
                                           'name.'.format(file_name=output_shape_file_name))

        payload['output_shape_file_name'] = output_shape_file_name

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def delineate_watershed(self, input_raster_url_path, threshold, output_raster, output_outlet_shapefile,
                            epsg_code=None, outlet_point_x=None, outlet_point_y=None,
                            input_outlet_shapefile_url_path=None, save_as=None):
        """
        Delineate watershed either using an outlet shapefile, or outlet X and Y coordinates

        :param input_raster_url_path: url file path for the raster file (user owned) on the HydroDS api server for
                                      which to delineate watershed
        :type input_raster_url_path: string
        :param threshold: threshold value to be used
        :type threshold: integer
        :param output_raster: file name for the delineated watershed raster file (if there is file already with the s
                              ame name it will be overwritten)
        :type output_raster: string
        :param output_outlet_shapefile: name for the outlet shapefile
        :type output_outlet_shapefile: string
        :param epsg_code: EPSG code to use for projection (required if not using input_outlet_shapefile_url_path)
        :type epsg_code: integer
        :param outlet_point_x: X-coordinate of the outlet point (required if not using input_outlet_shapefile_url_path)
        :type outlet_point_x: float
        :param outlet_point_y: Y-coordinate of the outlet point (required if not using input_outlet_shapefile_url_path)
        :type outlet_point_y: float
        :param input_outlet_shapefile_url_path: url file path for the outlet shape file (user owned) on the HydroDS api
                                                server to be used for outlet location
        :type input_outlet_shapefile_url_path: string
        :param save_as: (optional) raster file name and file path to save the delineated watershed raster file locally
        :type save_as: string
        :return:a dictionary with key 'output_raster' and value of url path for the watershed raster file, and
                key 'output_outlet_shapefile' and value of url path for the outlet shapefile

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            # >>> using outlet point location
            hds_response_data = hds.delineate_watershed(input_raster_url_path=provide_input_raster_url_path_here,
                                                        outlet_point_x=111.787,
                                                        outlet_point_y=41.742,
                                                        threshold=60000,
                                                        epsg_code=2152,
                                                        output_raster='logan_watershed.tif',
                                                        output_outlet_shapefile='logan_outlet.shp',
                                                        save_as=r'C:\hydro-ds\delineated_ws.tif')

            # print url path of the delineated watershed raster file
            output_delineated_raster_url = hds_response_data['output_raster']
            print(output_delineated_raster_url)

            # print the url path of the outlet shapefile
            output_outlet_shapefile_url = hds_response_data['output_outlet_shapefile']
            print(output_outlet_shapefile_url)

            # >>> using outlet shape file
            hds_response_data = hds.delineate_watershed(input_raster_url_path=raster_url,
                                                        input_outlet_shapefile_url_path=provide_outlet_shapefile_url_path_here,
                                                        threshold=60000,
                                                        output_raster='logan_watershed.tif',
                                                        output_outlet_shapefile='logan_outlet.shp',
                                                        save_as=r'C:\hydro-ds\delineated_ws.tif')

            # print url path of the delineated watershed raster file
            output_delineated_raster_url = hds_response_data['output_raster']
            print(output_delineated_raster_url)

            # print the url path of the outlet shapefile
            output_outlet_shapefile_url = hds_response_data['output_outlet_shapefile']
            print(output_outlet_shapefile_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(
                file_name=output_raster))

        if not self._is_file_name_valid(output_outlet_shapefile, ext='.shp'):
            raise HydroDSArgumentException("{file_name} is not a valid shapefile name".format(
                file_name=output_outlet_shapefile))
        try:
            int(threshold)
        except TypeError:
            raise HydroDSArgumentException("A value for threshold must be an integer number")

        if input_outlet_shapefile_url_path is None:
            if outlet_point_x is None:
                raise HydroDSArgumentException("A value for outlet_point_x is missing")
            else:
                try:
                    float(outlet_point_x)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_x must be a decimal number")

            if outlet_point_y is None:
                raise HydroDSArgumentException("A value for outlet_point_y is missing")
            else:
                try:
                    float(outlet_point_y)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_y must be a decimal number")

            if epsg_code is None:
                raise HydroDSArgumentException("A value for epsg_code is missing")
            else:
                try:
                    int(epsg_code)
                except TypeError:
                    raise HydroDSArgumentException("A value for epsg_code must be an integer")

        if input_outlet_shapefile_url_path:
            url = self._get_dataservice_specific_url(service_name='delineatewatershedatshape')
            payload = {'stream_threshold': threshold, 'input_DEM_raster': input_raster_url_path,
                       'input_outlet_shapefile': input_outlet_shapefile_url_path,
                       'output_raster': output_raster, 'output_outlet_shapefile': output_outlet_shapefile}
        else:
            url = self._get_dataservice_specific_url(service_name='delineatewatershedatxy')
            payload = {'epsg_code': epsg_code, 'stream_threshold': threshold, 'outlet_point_x': outlet_point_x,
                       'outlet_point_y': outlet_point_y, "input_DEM_raster": input_raster_url_path,
                       "output_raster": output_raster, 'output_outlet_shapefile': output_outlet_shapefile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)



    def resample_raster(self, input_raster_url_path, cell_size_dx, cell_size_dy, output_raster, resample='bilinear',
                        save_as=None):
        """
        Resample raster data

        :param input_raster_url_path: url file path of a raster file (user owned) on the HydroDs server that needs to
                                      be resampled
        :type input_raster_url_path: string
        :param cell_size_dx: width of the grid cell
        :type cell_size_dx: integer
        :param cell_size_dy: height of the grid cell
        :type cell_size_dy: integer
        :param output_raster: name for the output raster file (if there is file already with the same name it will be
                              overwritten)
        :type output_raster: string
        :param resample: resampling method (e.g., near, bilinear) (default is 'bilinear')
        :type resample: string
        :param save_as: (optional) raster file name and file path to save the delineated watershed raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the generated raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.resample_raster(input_raster_url_path=provide_input_raster_url_path_here,
                                                cell_size_dx=50, cell_size_dy=50, resample='near',
                                                output_raster='resample_spawn.tif')

            output_resample_raster_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_resample_raster_url)
        """
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_raster))

        if not isinstance(cell_size_dx, int):
            raise  HydroDSArgumentException("cell_size_dx must be an integer value")

        if not isinstance(cell_size_dy, int):
            raise  HydroDSArgumentException("cell_size_dy must be an integer value")

        resample = resample.lower()
        self._validate_resample_input(resample)

        url = self._get_dataservice_specific_url('resampleraster')
        payload = {"input_raster": input_raster_url_path, 'dx': cell_size_dx, 'dy': cell_size_dy, 'resample': resample,
                   'output_raster': output_raster}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def project_resample_raster(self, input_raster_url_path, cell_size_dx, cell_size_dy, output_raster, utm_zone=None,
                                epsg_code=None, resample='near',  save_as=None):

        """
        Project and resample a raster

        :param input_raster_url_path: url file path for the (user owned) raster on the HydroDs api server to be
                                      projected and resampled
        :type input_raster_url_path: string
        :param cell_size_dx: cell width
        :type cell_size_dx: integer
        :param cell_size_dy:  cell height
        :type cell_size_dy: integer
        :param output_raster: name for the output (projected/resampled) raster file (if there is file already with the
                              same name it will be overwritten)
        :type output_raster: string
        :param utm_zone:  UTM zone value to be used for projection (required if epsg_code is None)
        :type utm_zone: integer
        :param epsg_code: EPSG code value to be used for projection (required if utm_zone is None)
        :type epsg_code: integer
        :param resample: resample method (e.g., near, bilinear) (default is 'near')
        :type resample: string
        :param save_as: (optional) raster file name and file path to save the projected/resampled raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the projected raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)

            # using UTM based projection
            response_data = hds.project_resample_raster(input_raster_url_path=provide_input_raster_url_path_here,
                                                        cell_size_dx=100, cell_size_dy=100, utm_zone=12,
                                                        output_raster='project_resample_utm.tif', resample='bilinear')
            output_proj_resample_utm_raster_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_proj_resample_utm_raster_url)

            # using EPSG based projection
            response_data = hds.project_resample_raster(input_raster_url_path='input_raster_url_path', cell_size_dx=100,
                                                        cell_size_dy=100, epsg_code=2152,
                                                        output_raster='project_resample_epsg.tif', resample='bilinear')

            output_proj_resample_epsg_raster_url = response_data['output_raster']
            # print the url path for the generated raster file
            print(output_proj_resample_epsg_raster_url)

        """
        if save_as:
            self._validate_file_save_as(save_as)

        if utm_zone is None and epsg_code is None:
            raise HydroDSArgumentException("A value for either utm_zone or epsg_code is required")

        if utm_zone and epsg_code:
            raise HydroDSArgumentException("A value for either utm_zone or epsg_code is needed and not both")

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        if not isinstance(cell_size_dx, int):
            raise HydroDSArgumentException("cell_size_dx value must be an integer")

        if not isinstance(cell_size_dy, int):
            raise HydroDSArgumentException("cell_size_dy value must be an integer")

        url = None
        payload = {"input_raster": input_raster_url_path, 'dx': cell_size_dx, 'dy': cell_size_dy,
                   'output_raster': output_raster}
        resample = resample.lower()
        self._validate_resample_input(resample)
        payload['resample'] = resample

        if utm_zone:
            if not isinstance(utm_zone, int):
                raise HydroDSArgumentException("utm_zone value must be an integer")
            payload['utm_zone'] = utm_zone
            url = self._get_dataservice_specific_url('projectresamplerasterutm')

        if epsg_code:
            if not isinstance(epsg_code, int):
                raise HydroDSArgumentException("epsg_code value must be an integer")
            payload['epsg_code'] = epsg_code
            url = self._get_dataservice_specific_url('projectresamplerasterepsg')

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def subset_project_resample_raster(self, input_raster, left, top, right, bottom, cell_size_dx,
                                       cell_size_dy, output_raster, resample='near', epsg_code=None, save_as=None):
        """
        Subset, project, and resample a raster file

        :param input_raster: raster file to subset from (this can either be a url path for the user file on the HydroDS
                             api server or name of a relevant supported data resource file on the HydroDS api server)
        :param left: x-coordinate of the left-top corner of the bounding box
        :type left: float
        :param top: y-coordinate of the left-top corner of the bounding box
        :type top: float
        :param right: x-coordinate of the right-bottom corner of the bounding box
        :type right: float
        :param bottom: y-coordinate of the right-bottom corner of the bounding box
        :type bottom: float
        :param cell_size_dx: grid cell width
        :type cell_size_dx: integer
        :param cell_size_dy: grid cell height
        :type cell_size_dy: integer
        :param output_raster: name for the output (subsetted) raster file (if there is file already with the same name
                              it will be overwritten)
        :type output_raster: string
        :param epsg_code: (optional) EPSG code value to be used for projection (if not provided, projection will be
                          based on calculated UTM zone value)
        :type epsg_code: integer
        :param resample: (optional) resample method (e.g., near, bilinear) (default 'near')
        :type resample: string
        :param save_as: (optional) file name and file path to save the subsetted/projected/resampled raster file
                        locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the generated raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            input_raster = "nedWesternUS.tif"   #DEM of western USA (HydroDS supported data)

            # >>> using UTM based projection
            response_data = hds.subset_project_resample_raster(input_raster=input_raster, left=-111.97, top=42.11,
                                                               right=-111.35, bottom=41.66, cell_size_dx=100,
                                                               cell_size_dy=100, resample='bilinear',
                                                               output_raster='subset_project_resample_logan_utm.tif')

            output_subset_proj_resample_utm_raster_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_subset_proj_resample_utm_raster_url)

            # >>> using EPSG based projection
            response_data = hds.subset_project_resample_raster(input_raster=input_raster, left=-111.97, top=42.11,
                                                               right=-111.35, bottom=41.66, cell_size_dx=100,
                                                               cell_size_dy=100, resample='bilinear', epsg_code=2152,
                                                               output_raster='subset_project_resample_logan_epsg.tif')

            output_subset_proj_resample_epsg_raster_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_subset_proj_resample_epsg_raster_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        self._validate_boundary_box(bottom, left, right, top)

        if not isinstance(cell_size_dx, int):
            raise HydroDSArgumentException("cell_size_dx value must be an integer")

        if not isinstance(cell_size_dy, int):
            raise HydroDSArgumentException("cell_size_dy value must be an integer")

        resample = resample.lower()
        self._validate_resample_input(resample)

        payload = {"input_raster": input_raster, 'xmin': left, 'ymin': bottom, 'xmax': right, 'ymax': top,
                   'dx': cell_size_dx, 'dy': cell_size_dy, 'output_raster': output_raster, 'resample': resample}

        if epsg_code:
            if not isinstance(epsg_code, int):
                raise HydroDSArgumentException("epsg_code value must be an integer")
            payload['epsg_code'] = epsg_code
            url = self._get_dataservice_specific_url('subsetprojectresamplerasterepsg')
        else:
            url = self._get_dataservice_specific_url('subsetprojectresamplerasterutm')

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def resample_netcdf(self, input_netcdf_url_path, ref_netcdf_url_path, variable_name, output_netcdf,
                        save_as=None):
        """
        Resample a netcdf file

        :param input_netcdf_url_path: url file path of netcdf file (user owned) on HydroDS api server which needs to be
                                      resampled
        :type input_netcdf_url_path: string
        :param ref_netcdf_url_path: url file path of a netcdf file (user owned) on HydroDs api server to be used as the
                                    reference for resampling
        :type ref_netcdf_url_path: string
        :param output_netcdf: name for the output netcdf file (if there is file already with the same name it will be
                              overwritten)
        :type output_netcdf: string
        :param  variable_name: name of the variable in the input netcdf to be used for resampling
        :type variable_name: string
        :param save_as: (optional) file name and file path to save the resampled netcdf  file locally
        :type save_as: string
        :return: a dictionary with key 'output_netcdf' and value of url path for the generated netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.resample_netcdf(input_netcdf_url_path=provide_input_netcdf_url_path_here,
                                        ref_netcdf_url_path=provide_ref_netcdf_url_path, variable_name='prcp',
                                        output_netcdf='resample_to_ref_prcp_spwan.nc')

            output_resampled_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_resampled_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('resamplenetcdftoreferencenetcdf')
        payload = {"input_netcdf": input_netcdf_url_path, 'reference_netcdf': ref_netcdf_url_path,
                   'variable_name': variable_name, 'output_netcdf': output_netcdf}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def convert_netcdf_units(self, input_netcdf_url_path, output_netcdf, variable_name, variable_new_units=' ',
                             multiplier_factor=1, offset=0, save_as=None):
        """
        Convert netcdf data to a specified unit, A new netcdf file is generated with the converted data

        :param input_netcdf_url_path: url file path of netcdf file on HydroDS server for which variable units need to
                                      be changed
        :type input_netcdf_url_path: string
        :param output_netcdf: name for the output netcdf file with variable data in converted units (if there is file
                              already with the same name it will be overwritten)
        :type output_netcdf: string
        :param  variable_name: name of the variable in the input netcdf for which units to be converted
        :type variable_name: string
        :param variable_new_units: (optional) name for the converted unit
        :type variable_new_units: string
        :param multiplier_factor: (optional) factor by which the units to be converted (default is 1)
        :type multiplier_factor: float
        :param offset: (optional) additive factor (default is 0)
        :type offset: float
        :param save_as: (optional) file name and file path to save the generated netcdf file locally
        :return: a dictionary with key 'output_netcdf' and value of url path for the output netcdf file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified netcdf input file doesn't exist on HydroDS server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            input_netcdf_url_path = 'http://hydro-ds.uwrl.usu.edu:20199/files/data/user_2/subset_netcdf_to_spawn.nc'

            response_data = hds.convert_netcdf_units(input_netcdf_url_path=provide_input_netcdf_url_path_here,
                                                     output_netcdf='converted_units_spwan.nc',
                                                     variable_name='prcp', variable_new_units="m/hr",
                                                     multiplier_factor=0.00004167, offset=0)

            output_netcdf_url = response_data['output_netcdf']

            # print the url path for the generated netcdf file
            print(output_netcdf_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_netcdf, ext='.nc'):
            raise HydroDSArgumentException("{file_name} is not a valid netcdf file".format(file_name=output_netcdf))

        url = self._get_dataservice_specific_url('convertnetcdfunits')
        payload = {"input_netcdf": input_netcdf_url_path, 'output_netcdf': output_netcdf,
                   'variable_name': variable_name, 'variable_new_units': variable_new_units,
                   'multiplier_factor': multiplier_factor, 'offset': offset}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def upload_file_irods(self, file_to_upload):
        if not os.path.isfile(file_to_upload):
            raise Exception("iRODS upload file error: Specified file to upload (%s) does not exist." % file_to_upload)

        file_name = os.path.basename(file_to_upload)
        file_url_path = self._irods_rest_base_url + '/fileContents/usu/home/rods/' + file_name
        headers = {'accept': 'application/json'}
        with open(file_to_upload, 'rb') as upload_file_obj:
            response = self._requests.post(file_url_path, data={'uploadFile': file_name},
                                          files={'file': upload_file_obj}, auth=(self._irods_username, self._irods_password),
                                          headers=headers)

        if response.status_code != requests.codes.ok:
            raise Exception("Failed to upload to iRODS." + response.reason + " " + response.content)

        response_dict = json.loads(response.content)
        uploaded_file_path = response_dict['dataPath']
        service_req = ServiceRequest(service_name='upload_file', service_id_name='',
                                     service_id_value='', service_status='success', file_path=uploaded_file_path)
        _ServiceLog.add(service_req)
        self.save_service_call_history()
        return service_req

    def upload_file(self, file_to_upload):
        """
        Upload a file to HydroDS api server

        :param file_to_upload: file name and path for the file to upload from
        :type file_to_upload: string
        :return: url of the uploaded file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.upload_file(file_to_upload='E:\Scratch\param-test-pk.dat')
            uploaded_file_url = response_data

            # print the url path for the uploaded file
            print(uploaded_file_url)
        """

        if not os.path.isfile(file_to_upload):
            raise HydroDSArgumentException("Specified file to upload (%s) does not exist." % file_to_upload)

        if not os.access(file_to_upload, os.R_OK):
            raise HydroDSArgumentException("You don't have read access to the file (%s) to be uploaded."
                                           % file_to_upload)
        url = self._get_dataservice_specific_url('myfiles/upload')
        with open(file_to_upload, 'rb') as upload_file_obj:
            response = self._make_data_service_request(url=url, http_method='POST', files={'file': upload_file_obj})

        return self._process_dataservice_response(response, save_as=None)

    def download_file(self, file_url_path, save_as):
        """
        Download a file from the HydroDS api server

        :param file_url_path: HydroDS url for the file to be downloaded
        :type file_url_path: string
        :param save_as: file name and file path to save the downloaded file
        :type save_as: string
        :return: None

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified file to download does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            hds.download_file(file_url_path=provide_download_file_url_path_here, save_as=r'C:\hydro-ds\nlcd_proj_spwan.tif')

            print("File download was successful")

        """
        self._validate_file_save_as(save_as)

        with open(save_as, 'wb') as file_obj:
            response = requests.get(file_url_path, stream=True, auth=self._hg_auth)

            if not response.ok:
                # raise appropriate HydroDS exception
                self._process_dataservice_response(response)

            for block in response.iter_content(1024):
                if not block:
                    break
                file_obj.write(block)

    def zip_files(self, files_to_zip, zip_file_name, save_as=None):
        """
        Create a zip file from a list of user files on HydroDS

        :param files_to_zip: a list of user file names on the HydroDS which need to be zipped
        :type files_to_zip: a list
        :param zip_file_name: name of output the zip file (if there is file already with the same name it will be
                              overwritten)
        :type zip_file_name: string
        :param save_as: (optional) file name and file path to save the zipped file locally
        :type save_as: string
        :return: a dictionary with key of 'zip_file_name' and value of url file path the zip file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotFoundException: specified input file(s) does not exist on HydroDS

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            files_to_zip = ['subset.nc', 'projected.tif']
            response_data = hds.zip_files(files_to_zip=files_to_zip, zip_file_name='test_zipping.zip')
            output_zip_file_url = response_data['zip_file_name']

            # print the url path for the generated zip file
            print(output_zip_file_url)
        """

        if save_as:
            self._validate_file_save_as(save_as)

        if type(files_to_zip) is not list:
            raise HydroDSArgumentException("The value for the parameter files_to_zip must be a list")

        if not self._is_file_name_valid(zip_file_name, ext='.zip'):
            raise HydroDSArgumentException('{file_name} is not a valid zip file name.'.format(file_name=zip_file_name))

        file_names = ','.join(files_to_zip)
        url = self._get_dataservice_specific_url('myfiles/zip')
        payload = {"file_names": file_names, 'zip_file_name': zip_file_name}
        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def hydrogate_download_file_from_irods(self, file_url_path, save_as):
        self._check_user_irods_authentication()
        if not self._validate_file_save_as(save_as):
            return
        file_url_path = self._irods_rest_base_url + '/fileContents' + file_url_path
        with open(save_as, 'wb') as file_obj:
            response = requests.get(file_url_path, stream=True, auth=(self._irods_username, self._irods_password))

            if not response.ok:
                # Something went wrong
                raise Exception("HydroGate error: Error in downloading the file." + response.reason + " " + response.content)

            for block in response.iter_content(1024):
                if not block:
                    break
                file_obj.write(block)

        service_req = ServiceRequest(service_name='download_file', service_id_name='',
                                     service_id_value='', service_status='success', file_path=save_as)
        _ServiceLog.add(service_req)
        self.save_service_call_history()
        return service_req

    def download_file_from_hydrogate(self, hg_file_url_path, save_as):
        # no authentication needed for downloading the file
        self._validate_file_save_as(save_as)

        download_file_name = hg_file_url_path.split('/')[-1]
        hg_download_file_url_path = 'http://129.123.41.158:20198/{file_name}'.format(file_name=download_file_name)
        with open(save_as, 'wb') as file_obj:
            response = requests.get(hg_download_file_url_path, stream=True)
            if not response.ok:
                # Something went wrong
                raise Exception("HydroGate error: Error in downloading the file." + response.reason + " " + response.content)

            for block in response.iter_content(1024):
                if not block:
                    break
                file_obj.write(block)

    def set_hydroshare_account(self, username, password):
        self._hydroshare_auth = (username, password)

    def create_hydroshare_resource(self, file_name, resource_type, title=None, abstract=None, keywords=None):
        """
        Make a user file on HydroDS as a new resource in HydroShare

        :param file_name: name of user file on the HydroDS api server to be made as a resource in HydroShare
        :type file_name: string
        :param resource_type: type of resource to be created in HydroShare
        :type resource_type: string
        :param title: (optional) title of the new resource to be created in HydroShare
        :type title: string
        :param abstract: (optional) abstract of the new resource to be created in HydroShare
        :type abstract: string
        :param keywords: (optional) keywords for the new resource to be created in HydroShare
        :type keywords: list
        :return: a dictionary with keys ('resource_id', 'resource_type') that has value for resource id and resource
                 type of the HydroShare resource

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified file url path failed to resolve

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)

            # set hydroshare user account
            hds.set_hydroshare_account(username=your_hydroshare_username, password=your_hydroshare_password)

            # this a file you must own on HydroDS to make that as a new HydroShare resource
            file_to_use_for_hydroshare_resource = 'logan_ws.tif'
            response_data = hds.create_hydroshare_resource(file_name=file_to_use_for_hydroshare_resource,
                                                   resource_type='GenericResource',
                                                   title='Resource created from HydroDS by pk',
                                                   abstract="Testing creation resource from HydroDS",
                                                   keywords=['HydroShare', 'HydroDS'])

            # print id of the resource created in HydroShare
            print(response_data['resource_id'])

            # print type of of the resource created in HydroShare
            print(response_data['resource_type'])
        """

        if not self._hydroshare_auth:
            raise HydroDSNotAuthenticatedException("You don't have access to HydroShare. Set your HydroShare login account "
                                                   "using the function 'set_hydroshare_account()'")

        url = self._get_dataservice_specific_url('hydroshare/createresource')
        payload = {'file_name': file_name, 'resource_type': resource_type, 'hs_username': self._hydroshare_auth[0],
                   'hs_password': self._hydroshare_auth[1]}
        if title:
            payload['title'] = title
        if abstract:
            payload['abstract'] = abstract

        if keywords:
            if not isinstance(keywords, list):
                raise HydroDSArgumentException('keywords must be a list')

            keywords = ','.join(keywords)
            payload['keywords'] = keywords

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as=None)

   ######################Start of TOPNET function ####################


    def download_streamflow(self, usgs_gage, start_year, end_year, output_streamflow, save_as=None):


        if save_as:
            self._validate_file_save_as(save_as)
        try:
            int(usgs_gage)
        except:
            raise Exception("Error:Invalid start year. Year must be an integer value.")
        try:
           int(start_year)
        except:
            raise Exception("Error:Invalid start year. Year must be an integer value.")
        try:
            int(end_year)
        except:
            raise Exception("Error:Invalid end year. Year must be an integer value.")

        if not self._is_file_name_valid(output_streamflow, ext='.dat'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_streamflow))

        url = self._get_dataservice_specific_url('downloadstreamflow')
        if end_year > start_year:
             payload = {"USGS_gage": usgs_gage, 'Start_Year': start_year, "End_Year": end_year,"output_streamflow":output_streamflow}
        else:
             payload = {"USGS_gage": usgs_gage, 'Start_Year': end_year, "End_Year": start_year,"output_streamflow":output_streamflow}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def delineate_watershed_peuker_douglas(self, input_raster_url_path, threshold, peuker_min_threshold,peuker_max_threshold,peuker_number_threshold,output_watershed_raster,output_outlet_shapefile,output_treefile,output_coordfile,output_streamnetfile,output_slopearea_raster,output_distance_raster,
                            epsg_code=None, outlet_point_x=None, outlet_point_y=None, input_outlet_shapefile_url_path=None, save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_watershed_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_watershed_raster))


        if not self._is_file_name_valid(output_slopearea_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_slopearea_raster))

        if not self._is_file_name_valid(output_distance_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_distance_raster))

        if not self._is_file_name_valid(output_treefile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_treefile))

        if not self._is_file_name_valid(output_coordfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_coordfile))


        if not self._is_file_name_valid(output_outlet_shapefile, ext='.shp'):
            raise HydroDSArgumentException("{file_name} is not a valid shapefile name".format(file_name=output_outlet_shapefile))
        if not self._is_file_name_valid(output_streamnetfile, ext='.shp'):
            raise HydroDSArgumentException("{file_name} is not a valid shapefile name".format(file_name=output_outlet_shapefile))
        try:
            int(threshold)
        except TypeError:
            raise HydroDSArgumentException("A value for threshold must be an integer number")

        if input_outlet_shapefile_url_path is None:
            if outlet_point_x is None:
                raise HydroDSArgumentException("A value for outlet_point_x is missing")
            else:
                try:
                    float(outlet_point_x)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_x must be a decimal number")

            if outlet_point_y is None:
                raise HydroDSArgumentException("A value for outlet_point_y is missing")
            else:
                try:
                    float(outlet_point_y)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_y must be a decimal number")


        url = self._get_dataservice_specific_url(service_name='watersheddelineation')
        if input_outlet_shapefile_url_path:
           payload = {'Src_threshold': threshold, 'Min_threshold': peuker_min_threshold,'Max_threshold': peuker_max_threshold,'Number_threshold':peuker_number_threshold,'DEM_Raster': input_raster_url_path,
                       'Outlet_shapefile': input_outlet_shapefile_url_path,
                       'output_watershedfile': output_watershed_raster, 'output_pointoutletshapefile': output_outlet_shapefile,'output_treefile':output_treefile,'output_coordfile':output_coordfile,'output_streamnetfile':output_streamnetfile,'output_slopareafile':output_slopearea_raster,'output_distancefile':output_distance_raster}
        else:
            response_data = self.create_outlet_shapefile(point_x=outlet_point_x, point_y=outlet_point_y, output_shape_file_name='outlet-shape.shp')
            output_outlet_shapefile_url = response_data['output_shape_file_name']
            #url = self._get_dataservice_specific_url(service_name='watersheddelineation')
            payload = {'Src_threshold': threshold, 'Min_threshold': peuker_min_threshold,'Max_threshold': peuker_max_threshold,'Number_threshold':peuker_number_threshold,'DEM_Raster': input_raster_url_path,
                       'outlet_shapefile': output_outlet_shapefile_url,
                       'output_watershedfile': output_watershed_raster, 'output_pointoutletshapefile': output_outlet_shapefile,'output_treefile':output_treefile,'output_coordfile':output_coordfile,'output_streamnetfile':output_streamnetfile,'output_slopareafile':output_slopearea_raster,'output_distancefile':output_distance_raster}



        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def get_daymet_data(self, input_raster_url_path,start_year, end_year,output_gagefile,output_rainfile,output_temperaturefile,output_cliparfile,save_as=None):


        if save_as:
            self._validate_file_save_as(save_as)
        if not self._is_file_name_valid(output_gagefile, ext='.shp'):
            raise HydroDSArgumentException("{file_name} is not a valid shapefile name".format(file_name=output_gagefile))

        if not self._is_file_name_valid(output_rainfile, ext='.dat'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_rainfile))

        if not self._is_file_name_valid(output_temperaturefile, ext='.dat'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_temperaturefile))

        if not self._is_file_name_valid(output_cliparfile, ext='.dat'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_cliparfile))


        try:
            int(start_year)
        except:
            raise Exception("Error:Invalid start year. Year must be an integer value.")

        try:
            int(end_year)
        except:
            raise Exception("Error:Invalid end year. Year must be an integer value.")

        url = self._get_dataservice_specific_url('downloadclimatedata')

        if end_year > start_year:
            payload = {"Watershed_Raster": input_raster_url_path,
                       "Start_Year": start_year, "End_Year": end_year,
                       "output_gagefile":output_gagefile,
                       "output_rainfile":output_rainfile,
                       "output_temperaturefile":output_temperaturefile,
                       "output_cliparfile":output_cliparfile}
        else:
            payload = {"Watershed_Raster": input_raster_url_path,
                       "Start_Year": end_year, "End_Year": start_year,
                       "output_gagefile":output_gagefile,
                       "output_rainfile":output_rainfile,
                       "output_temperaturefile":output_temperaturefile,"output_cliparfile":output_cliparfile}

        response = self._make_data_service_request(url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def get_soil_data(self,input_watershed_raster_url_path,output_f_raster,output_k_raster,output_dth1_raster,
                     output_dth2_raster,output_psif_raster,output_sd_raster,output_tran_raster,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_f_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_f_raster))

        if not self._is_file_name_valid(output_k_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_k_raster))
        if not self._is_file_name_valid(output_dth1_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth1_raster))
        if not self._is_file_name_valid(output_dth2_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth2_raster))
        if not self._is_file_name_valid(output_psif_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_psif_raster))
        if not self._is_file_name_valid(output_sd_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_sd_raster))
        if not self._is_file_name_valid(output_tran_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_tran_raster))

        url = self._get_dataservice_specific_url(service_name='downloadsoildata')
        payload = {'Watershed_Raster':input_watershed_raster_url_path, 'output_f_file': output_f_raster,'output_k_file': output_k_raster,
                       'output_dth1_file': output_dth1_raster,'output_dth2_file': output_dth2_raster, 'output_psif_file': output_psif_raster,
                       'output_sd_file': output_sd_raster,'output_tran_file': output_tran_raster}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)




    def reachlink(self, input_DEM_raster_url_path,input_watershed_raster_url_path,input_treefile,input_coordfile,output_reachfile,output_nodefile,output_reachareafile,output_rchpropertiesfile,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_reachfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_reachfile))


        if not self._is_file_name_valid(output_nodefile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_nodefile))

        if not self._is_file_name_valid(output_rchpropertiesfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_rchpropertiesfile))
        if not self._is_file_name_valid(output_reachareafile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_reachareafile))



        url = self._get_dataservice_specific_url(service_name='reachlink')
        payload = {'DEM_Raster': input_DEM_raster_url_path,'Watershed_Raster':input_watershed_raster_url_path,'treefile':input_treefile,'coordfile':input_coordfile,
                   'output_reachfile': output_reachfile,'output_nodefile': output_nodefile,'output_reachareafile': output_reachareafile,'output_rchpropertiesfile':output_rchpropertiesfile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def distance_wetness_distribution(self, input_watershed_raster_url_path,input_sloparearatio_raster_url_path,input_distancnetostream_raster_url_path,output_distributionfile,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)


        if not self._is_file_name_valid(output_distributionfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_distributionfile))


        url = self._get_dataservice_specific_url(service_name='dist_wetness_distribution')
        payload = {'Watershed_Raster':input_watershed_raster_url_path,'SaR_Raster':input_sloparearatio_raster_url_path,'Dist_Raster':input_distancnetostream_raster_url_path,
                   'output_distributionfile': output_distributionfile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def getlanduse_lancoverdata(self, input_raster_url_path,output_raster,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)
        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(
                file_name=output_raster))

        url = self._get_dataservice_specific_url(service_name='getlanduselandcoverdata')
        payload = {'Watershed_Raster':input_raster_url_path,'output_LULCRaster':output_raster}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def createlatlonfromxy(self, input_watershed_raster_url_path,output_file,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_file, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_file))

        url = self._get_dataservice_specific_url(service_name='createlatlonfromxy')
        payload = {'Watershed_Raster': input_watershed_raster_url_path,'output_latlonfromxyfile':output_file}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def createparameterlistfile(self, input_watershed_raster_url_path,output_file,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)
        if not self._is_file_name_valid(output_file, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_file))

        url = self._get_dataservice_specific_url(service_name='createparmfile')
        payload = {'Watershed_Raster': input_watershed_raster_url_path,'output_parspcfile':output_file}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)



    def create_rainweight(self, input_watershed_raster_url_path, input_raingauge_shapefile_url_path, input_annual_rainfile,input_nodelink_file,output_rainweightfile,
                           save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_rainweightfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_rainweightfile))

        url = self._get_dataservice_specific_url(service_name='createrainweight')
        payload = { "Watershed_Raster":input_watershed_raster_url_path,
                   'Rain_gauge_shapefile': input_raingauge_shapefile_url_path,'annual_rainfile':input_annual_rainfile,'nodelink_file':input_nodelink_file,'output_rainweightfile':output_rainweightfile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)



    def create_basinparamterfile(self,input_DEM_raster_url_path,input_watershed_raster_url_path,input_f_url_path,input_dth1_url_path,input_dth2_url_path,input_k_url_path,
       input_sd_url_path,input_psif_url_path,input_tran_url_path,
       input_lulc_url_path,input_lutlc_url_path,input_lutkc_url_path,input_parameterspecfile_url_path,input_nodelinksfile_url_path, output_basinparameterfile,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_basinparameterfile, ext='.txt'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_basinparameterfile))

        url = self._get_dataservice_specific_url(service_name='createbasinparameter')
        payload = {'DEM_Raster':input_DEM_raster_url_path,'f_raster':input_f_url_path,'k_raster':input_k_url_path,
                    'dth1_raster':input_dth1_url_path,'dth2_raster':input_dth2_url_path,'sd_raster':input_sd_url_path,'psif_raster':input_psif_url_path,
                    'tran_raster':input_tran_url_path,'lulc_raster':input_lulc_url_path, 'lutlc':input_lutlc_url_path,'lutkc':input_lutkc_url_path,
                    'Watershed_Raster':input_watershed_raster_url_path,'parameter_specficationfile': input_parameterspecfile_url_path,
                    'nodelinksfile':input_nodelinksfile_url_path,'output_basinfile':output_basinparameterfile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    ##################################END OF TOPNET FUNCTION ################################


    ##################################START OF TOPKAPI FUNCTIONS ################################

    def subset_raster2(self, left, top, right, bottom, input_raster, output_raster, cell_size=None , save_as=None):
        """
        Subset raster data

        :param left: x-coordinate of the left-top corner of the bounding box
        :type left: float
        :param top: y-coordinate of the left-top corner of the bounding box
        :type top: float
        :param right: x-coordinate of the right-bottom corner of the bounding box
        :type right: float
        :param bottom: y-coordinate of the right-bottom corner of the bounding box
        :type bottom: float
        :param input_raster: raster file to subset from (this can either be a url path for the user file on the HydroDS
                             server or name of a relevant supported data file on the HydroDS server)
        :param output_raster: name for the output (subsetted) raster file (if there is file already with the same name
                              it will be overwritten)
        :type output_raster: string
        :param save_as: (optional) file name and file path to save the subsetted raster file locally
        :type save_as: string
        :return: a dictionary with key 'output_raster' and value of url path for the generated raster file

        :raises: HydroDSArgumentException: one or more argument failed validation at client side
        :raises: HydroDSBadRequestException: one or more argument failed validation on the server side
        :raises: HydroDSNotAuthenticatedException: provided user account failed validation
        :raises: HydroDSNotAuthorizedException: user making this request is not authorized to do so
        :raises: HydroDSNotFoundException: specified raster input file(s) does not exist on the server

        Example usage:
            hds = HydroDS(username=your_username, password=your_password)
            response_data = hds.subset_raster(left=-111.97, top=42.11, right=-111.35, bottom=41.66,
                                              input_raster='nedWesternUS.tif', output_raster='subset_dem_logan.tif')

            output_subset_dem_url = response_data['output_raster']

            # print the url path for the generated raster file
            print(output_subset_dem_url)
        """

        url = self._get_dataservice_specific_url(service_name='rastersubset2') ##
        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException('{file_name} is not a valid raster file '
                                           'name.'.format(file_name=output_raster))

        self._validate_boundary_box(bottom, left, right, top)

        payload = {'xmin': left, 'ymin': bottom, 'xmax': right, 'ymax': top, 'input_raster': input_raster,
                   'output_raster': output_raster, 'cell_size':cell_size}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def reclassifyrasterwithlut(self, input_raster, LUT=u'http://129.123.9.159:20199/files/data/user_6/LUT_NLCD2n.csv',  output_raster='reclassified_raster.tif',delimiter=',',  save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('reclassifyrasterwithlut')
        payload = {"input_raster": input_raster, 'LUT':LUT, 'delimiter':delimiter}
        self._is_file_name_valid(output_raster, ext='.tif')
        payload['output_raster'] = output_raster

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def runpytopkapi(self,user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage, timestep,threshold,
                     mask_fname,overland_manning_fname,hillslope_fname, dem_fname, channel_network_fname, flowdir_fname,
            pore_size_dist_fname, bubbling_pressure_fname, resid_moisture_content_fname, sat_moisture_content_fname, conductivity_fname, soil_depth_fname,
                     # rain_fname, et_fname, runoff_fname,
            output_zip='pytopkpai_model_files.zip',  save_as=None):

      if save_as:
         self._validate_file_save_as(save_as)

      url = self._get_dataservice_specific_url('runpytopkapi')
      payload = {'user_name':user_name, 'simulation_name':simulation_name, 'simulation_start_date':simulation_start_date,
                    'simulation_end_date':simulation_end_date, 'USGS_gage':USGS_gage, 'timestep':timestep,'threshold':threshold,
                   'hillslope_fname': hillslope_fname, 'dem_fname': dem_fname, 'channel_network_fname': channel_network_fname, 'overland_manning_fname':overland_manning_fname,
                   'mask_fname': mask_fname, 'flowdir_fname': flowdir_fname,  'pore_size_dist_fname': pore_size_dist_fname,
                   'bubbling_pressure_fname': bubbling_pressure_fname, 'resid_moisture_content_fname': resid_moisture_content_fname,
                   'sat_moisture_content_fname': sat_moisture_content_fname,'conductivity_fname':conductivity_fname,'soil_depth_fname':soil_depth_fname,
                   # 'rain_fname':rain_fname, 'et_fname':et_fname, 'runoff_fname':runoff_fname ,
                   'output_zip' : output_zip }

      self._is_file_name_valid(output_zip, ext='.zip')
      payload['output_zip'] = output_zip

      response = self._make_data_service_request(url=url, params=payload)
      return self._process_dataservice_response(response, save_as)

    def runpytopkapi2(self, user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage, timestep,
                     threshold,
                      outlet_y, outlet_x, box_topY, box_bottomY, box_rightX, box_leftX, timeseries_source,
                      cell_size, model_engine,
                     output_zip='pytopkpai_model_files.zip', save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('runpytopkapi2')
        payload = {'user_name': user_name, 'simulation_name': simulation_name,
                   'simulation_start_date': simulation_start_date,
                   'simulation_end_date': simulation_end_date, 'USGS_gage': USGS_gage, 'timestep': timestep,
                   'threshold': threshold,
                   'outlet_y': outlet_y,'outlet_x': outlet_x, 'box_topY':box_topY,'box_bottomY': box_bottomY,'box_rightX': box_rightX, 'box_leftX':box_leftX, 'timeseries_source':timeseries_source,
                   'cell_size': cell_size, 'model_engine':model_engine,

                   'output_zip': output_zip}

        self._is_file_name_valid(output_zip, ext='.zip')
        payload['output_zip'] = output_zip

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def runpytopkapi3(self, user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage,
                     timestep, threshold,
                     mask_fname, overland_manning_fname, hillslope_fname, dem_fname, channel_network_fname,
                     flowdir_fname,
                     pore_size_dist_fname, bubbling_pressure_fname, resid_moisture_content_fname,
                     sat_moisture_content_fname, conductivity_fname, soil_depth_fname,
                     # rain_fname, et_fname, runoff_fname,
                     output_txt='pytopkpai_model_files_metadata.txt', save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('runpytopkapi3')
        payload = {'user_name': user_name, 'simulation_name': simulation_name,
                   'simulation_start_date': simulation_start_date,
                   'simulation_end_date': simulation_end_date, 'USGS_gage': USGS_gage, 'timestep': timestep,
                   'threshold': threshold,
                   'hillslope_fname': hillslope_fname, 'dem_fname': dem_fname,
                   'channel_network_fname': channel_network_fname, 'overland_manning_fname': overland_manning_fname,
                   'mask_fname': mask_fname, 'flowdir_fname': flowdir_fname,
                   'pore_size_dist_fname': pore_size_dist_fname,
                   'bubbling_pressure_fname': bubbling_pressure_fname,
                   'resid_moisture_content_fname': resid_moisture_content_fname,
                   'sat_moisture_content_fname': sat_moisture_content_fname,
                   'conductivity_fname': conductivity_fname, 'soil_depth_fname': soil_depth_fname,
                   # 'rain_fname':rain_fname, 'et_fname':et_fname, 'runoff_fname':runoff_fname ,
                   'output_txt': output_txt}

        self._is_file_name_valid(output_txt, ext='.txt')
        payload['output_txt'] = output_txt

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def runpytopkapi4(self, user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage,
                     timestep, threshold,
                     mask_fname, overland_manning_fname, hillslope_fname, dem_fname, channel_network_fname,
                     flowdir_fname,
                     pore_size_dist_fname, bubbling_pressure_fname, resid_moisture_content_fname,
                     sat_moisture_content_fname, conductivity_fname, soil_depth_fname,
                     # rain_fname, et_fname, runoff_fname,
                      output_hs_rs_id_txt='pytopkpai_model_files_metadata.txt', output_q_sim_txt= 'output_q_sim.txt', save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('runpytopkapi4')
        payload = {'user_name': user_name, 'simulation_name': simulation_name,
                   'simulation_start_date': simulation_start_date.replace('-','/'),
                   'simulation_end_date': simulation_end_date.replace('-','/'),
                   'USGS_gage': USGS_gage, 'timestep': timestep,
                   'threshold': threshold,
                   'hillslope_fname': hillslope_fname, 'dem_fname': dem_fname,
                   'channel_network_fname': channel_network_fname, 'overland_manning_fname': overland_manning_fname,
                   'mask_fname': mask_fname, 'flowdir_fname': flowdir_fname,
                   'pore_size_dist_fname': pore_size_dist_fname,
                   'bubbling_pressure_fname': bubbling_pressure_fname,
                   'resid_moisture_content_fname': resid_moisture_content_fname,
                   'sat_moisture_content_fname': sat_moisture_content_fname,
                   'conductivity_fname': conductivity_fname, 'soil_depth_fname': soil_depth_fname,
                   # 'rain_fname':rain_fname, 'et_fname':et_fname, 'runoff_fname':runoff_fname ,
                   # 'output_hs_rs_id_txt': output_hs_rs_id_txt
                   }

        self._is_file_name_valid(output_hs_rs_id_txt, ext='.txt')
        payload['output_hs_rs_id_txt'] = output_hs_rs_id_txt
        payload['output_q_sim_txt'] = output_q_sim_txt


        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def runpytopkapi5(self, user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage,
                     timestep, threshold,
                     mask_fname, overland_manning_fname, hillslope_fname, dem_fname, channel_network_fname,
                     flowdir_fname,
                     pore_size_dist_fname, bubbling_pressure_fname, resid_moisture_content_fname,
                     sat_moisture_content_fname, conductivity_fname, soil_depth_fname,
                     rain_fname, et_fname,
                     output_response_txt='pytopkpai_responseJSON.txt',  save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('runpytopkapi5')
        payload = {'user_name': user_name, 'simulation_name': simulation_name,
                   'simulation_start_date': simulation_start_date.replace('-','/'),
                   'simulation_end_date': simulation_end_date.replace('-','/'),
                   'USGS_gage': USGS_gage, 'timestep': timestep,
                   'threshold': threshold,
                   'hillslope_fname': hillslope_fname, 'dem_fname': dem_fname,
                   'channel_network_fname': channel_network_fname, 'overland_manning_fname': overland_manning_fname,
                   'mask_fname': mask_fname, 'flowdir_fname': flowdir_fname,
                   'pore_size_dist_fname': pore_size_dist_fname,
                   'bubbling_pressure_fname': bubbling_pressure_fname,
                   'resid_moisture_content_fname': resid_moisture_content_fname,
                   'sat_moisture_content_fname': sat_moisture_content_fname,
                   'conductivity_fname': conductivity_fname, 'soil_depth_fname': soil_depth_fname,
                   'rain_fname':rain_fname,
                   'et_fname':et_fname,
                   # 'runoff_fname':runoff_fname ,
                   # 'output_hs_rs_id_txt': output_hs_rs_id_txt
                   }

        self._is_file_name_valid(output_response_txt, ext='.txt')
        payload['output_hs_rs_id_txt'] = output_response_txt



        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def runpytopkapi6(self, user_name, simulation_name, simulation_start_date, simulation_end_date, USGS_gage,
                     timestep, threshold,
                     mask_fname, overland_manning_fname, hillslope_fname, dem_fname, channel_network_fname,
                     flowdir_fname,
                     pore_size_dist_fname, bubbling_pressure_fname, resid_moisture_content_fname,
                     sat_moisture_content_fname, conductivity_fname, soil_depth_fname,
                     rain_fname, et_fname, timeseries_source='daymet',
                     output_response_txt='pytopkpai_responseJSON.txt',  save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('runpytopkapi6')
        payload = {'user_name': user_name, 'simulation_name': simulation_name,
                   'simulation_start_date': simulation_start_date.replace('-','/'),
                   'simulation_end_date': simulation_end_date.replace('-','/'),
                   'USGS_gage': USGS_gage, 'timestep': timestep,
                   'threshold': threshold,
                   'hillslope_fname': hillslope_fname, 'dem_fname': dem_fname,
                   'channel_network_fname': channel_network_fname, 'overland_manning_fname': overland_manning_fname,
                   'mask_fname': mask_fname, 'flowdir_fname': flowdir_fname,
                   'pore_size_dist_fname': pore_size_dist_fname,
                   'bubbling_pressure_fname': bubbling_pressure_fname,
                   'resid_moisture_content_fname': resid_moisture_content_fname,
                   'sat_moisture_content_fname': sat_moisture_content_fname,
                   'conductivity_fname': conductivity_fname, 'soil_depth_fname': soil_depth_fname,
                   'rain_fname':rain_fname,
                   'et_fname':et_fname,
                   # 'runoff_fname':runoff_fname ,
                   # 'output_hs_rs_id_txt': output_hs_rs_id_txt
                   }
        payload['timeseries_source']=timeseries_source

        self._is_file_name_valid(output_response_txt, ext='.txt')
        payload['output_hs_rs_id_txt'] = output_response_txt



        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)



    def modifypytopkapi(self,  fac_l, fac_ks, fac_n_o, fac_n_c,fac_th_s,
                pvs_t0 ,vo_t0 ,qc_t0 ,kc,
                hs_res_id, output_hs_rs_id_txt='pytopkpai_model_files_metadata.txt', output_q_sim_txt= 'output_q_sim.txt',
                save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('modifypytopkapi')
        payload = {
            'fac_l':fac_l, 'fac_ks':fac_ks, 'fac_n_o':fac_n_o, 'fac_n_c':fac_n_c, 'fac_th_s':fac_th_s,
            'pvs_t0':pvs_t0, 'vo_t0':vo_t0, 'qc_t0':qc_t0, 'kc':kc,
            'hs_res_id': hs_res_id,
            'output_hs_rs_id_txt':'pytopkpai_model_files_metadata.txt',
            'output_q_sim_txt' : 'output_q_sim.txt'
                   }

        self._is_file_name_valid(output_hs_rs_id_txt, ext='.txt')
        payload['output_hs_rs_id_txt'] = output_hs_rs_id_txt
        payload['output_q_sim_txt'] = output_q_sim_txt


        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def loadpytopkapi(self,
                      hs_res_id, output_hs_rs_id_txt='pytopkpai_model_files_metadata.txt',
                      output_q_sim_txt= 'output_q_sim_retreived.txt',
                        save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('loadpytopkapi')
        payload = {
            'hs_res_id': hs_res_id,
            'output_hs_rs_id_txt':output_hs_rs_id_txt,
            'output_q_sim_txt' : output_q_sim_txt
                   }

        self._is_file_name_valid(output_hs_rs_id_txt, ext='.txt')

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def delineatewatershedtogetcompleterasterset(self, input_raster_url_path, threshold, output_raster, output_outlet_shapefile,
                            epsg_code=None, outlet_point_x=None, outlet_point_y=None,
                            input_outlet_shapefile_url_path=None,
                           output_fill_raster='fel.tif', output_slope_raster='sd8.tif', output__flow_direction_raster='p.tif',
                           output_contributing_area_raster='ad8.tif', output_strahler_order_raster='ssa.tif',
                           output_stream_raster='src.tif' #, output_mannings_n_stream_raster = 'n_stream.tif'
                           ,save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(
                file_name=output_raster))

        if not self._is_file_name_valid(output_outlet_shapefile, ext='.shp'):
            raise HydroDSArgumentException("{file_name} is not a valid shapefile name".format(
                file_name=output_outlet_shapefile))
        try:
            int(threshold)
        except TypeError:
            raise HydroDSArgumentException("A value for threshold must be an integer number")

        if input_outlet_shapefile_url_path is None:
            if outlet_point_x is None:
                raise HydroDSArgumentException("A value for outlet_point_x is missing")
            else:
                try:
                    float(outlet_point_x)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_x must be a decimal number")

            if outlet_point_y is None:
                raise HydroDSArgumentException("A value for outlet_point_y is missing")
            else:
                try:
                    float(outlet_point_y)
                except TypeError:
                    raise HydroDSArgumentException("A value for outlet_point_y must be a decimal number")

            if epsg_code is None:
                raise HydroDSArgumentException("A value for epsg_code is missing")
            else:
                try:
                    int(epsg_code)
                except TypeError:
                    raise HydroDSArgumentException("A value for epsg_code must be an integer")

        if input_outlet_shapefile_url_path:
            url = self._get_dataservice_specific_url(service_name='delineatewatershedtogetcompleterasterset')
            payload = {'stream_threshold': threshold, 'input_DEM_raster': input_raster_url_path,
                       'input_outlet_shapefile': input_outlet_shapefile_url_path,
                       'output_raster': output_raster, 'output_outlet_shapefile': output_outlet_shapefile,
                       #'epsg_code': epsg_code,

                       'output_fill_raster': output_fill_raster, 'output_slope_raster': output_slope_raster,
                       'output__flow_direction_raster': output__flow_direction_raster, 'output_contributing_area_raster': output_contributing_area_raster,
                       'output_strahler_order_raster': output_strahler_order_raster, 'output_stream_raster': output_stream_raster,
                       # 'output_mannings_n_stream_raster':output_mannings_n_stream_raster
                       }

        else:

            url = self._get_dataservice_specific_url(service_name='delineatewatershedatxy')
            payload = {'epsg_code': epsg_code, 'stream_threshold': threshold, 'outlet_point_x': outlet_point_x,
                       'outlet_point_y': outlet_point_y, "input_DEM_raster": input_raster_url_path,
                       "output_raster": output_raster, 'output_outlet_shapefile': output_outlet_shapefile}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def downloadsoildataforpytopkapi(self,input_watershed_raster_url_path,output_f_raster='f.tif',output_k_raster='ko.tif',output_dth1_raster='dth1.tif',
                     output_dth2_raster='dth2.tif',output_psif_raster='psif.tif',output_sd_raster='sd.tif',output_tran_raster='trans.tif',
                                     output_bubbling_pressure_file='BBL.tif', output_pore_size_distribution_file="PSD.tif",
                                     output_residual_soil_moisture_file='RSM.tif', output_saturated_soil_moisture_file='SSM.tif',output_ksat_rawls_file='ksat_rawls.tif',
                                     save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_f_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_f_raster))

        if not self._is_file_name_valid(output_k_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_k_raster))
        if not self._is_file_name_valid(output_dth1_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth1_raster))
        if not self._is_file_name_valid(output_dth2_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth2_raster))
        if not self._is_file_name_valid(output_psif_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_psif_raster))
        if not self._is_file_name_valid(output_sd_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_sd_raster))
        if not self._is_file_name_valid(output_tran_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_tran_raster))

        if not self._is_file_name_valid(output_bubbling_pressure_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_bubbling_pressure_file))
        if not self._is_file_name_valid(output_pore_size_distribution_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_pore_size_distribution_file))
        if not self._is_file_name_valid(output_residual_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_residual_soil_moisture_file))
        if not self._is_file_name_valid(output_saturated_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_saturated_soil_moisture_file))
        if not self._is_file_name_valid(output_ksat_rawls_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_ksat_rawls_file))

        url = self._get_dataservice_specific_url(service_name='downloadsoildataforpytopkapi')
        payload = {'Watershed_Raster':input_watershed_raster_url_path, 'output_f_file': output_f_raster,'output_k_file': output_k_raster,
                       'output_dth1_file': output_dth1_raster,'output_dth2_file': output_dth2_raster, 'output_psif_file': output_psif_raster,
                       'output_sd_file': output_sd_raster,'output_tran_file': output_tran_raster,
                   'output_bubbling_pressure_file': output_bubbling_pressure_file, 'output_pore_size_distribution_file': output_pore_size_distribution_file,
                   'output_residual_soil_moisture_file': output_residual_soil_moisture_file, 'output_saturated_soil_moisture_file': output_saturated_soil_moisture_file,
                   'output_ksat_rawls_file':output_ksat_rawls_file
                   }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def downloadsoildataforpytopkapi2(self,input_watershed_raster_url_path,output_f_raster='f.tif',output_k_raster='ko.tif',output_dth1_raster='dth1.tif',
                     output_dth2_raster='dth2.tif',output_psif_raster='psif.tif',output_sd_raster='sd.tif',output_tran_raster='trans.tif',
                                     output_bubbling_pressure_file='BBL.tif', output_pore_size_distribution_file="PSD.tif",
                                     output_residual_soil_moisture_file='RSM.tif', output_saturated_soil_moisture_file='SSM.tif',
                                      output_ksat_rawls_file='ksat_rawls.tif',output_ksat_hz_file='ksat_hz.tif',
                                     save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        if not self._is_file_name_valid(output_f_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_f_raster))

        if not self._is_file_name_valid(output_k_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_k_raster))
        if not self._is_file_name_valid(output_dth1_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth1_raster))
        if not self._is_file_name_valid(output_dth2_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth2_raster))
        if not self._is_file_name_valid(output_psif_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_psif_raster))
        if not self._is_file_name_valid(output_sd_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_sd_raster))
        if not self._is_file_name_valid(output_tran_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_tran_raster))

        if not self._is_file_name_valid(output_bubbling_pressure_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_bubbling_pressure_file))
        if not self._is_file_name_valid(output_pore_size_distribution_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_pore_size_distribution_file))
        if not self._is_file_name_valid(output_residual_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_residual_soil_moisture_file))
        if not self._is_file_name_valid(output_saturated_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_saturated_soil_moisture_file))
        if not self._is_file_name_valid(output_ksat_rawls_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_ksat_rawls_file))

        url = self._get_dataservice_specific_url(service_name='downloadsoildataforpytopkapi2')
        payload = {'Watershed_Raster':input_watershed_raster_url_path, 'output_f_file': output_f_raster,'output_k_file': output_k_raster,
                       'output_dth1_file': output_dth1_raster,'output_dth2_file': output_dth2_raster, 'output_psif_file': output_psif_raster,
                       'output_sd_file': output_sd_raster,'output_tran_file': output_tran_raster,
                   'output_bubbling_pressure_file': output_bubbling_pressure_file, 'output_pore_size_distribution_file': output_pore_size_distribution_file,
                   'output_residual_soil_moisture_file': output_residual_soil_moisture_file, 'output_saturated_soil_moisture_file': output_saturated_soil_moisture_file,
                   'output_ksat_rawls_file':output_ksat_rawls_file, 'output_ksat_hz_file':output_ksat_hz_file,
                   }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def downloadsoildataforpytopkapi3(self,input_watershed_raster_url_path,output_dth1_raster='dth1.tif',
                     output_dth2_raster='dth2.tif',output_psif_raster='psif.tif',output_sd_raster='sd.tif',
                                     output_bubbling_pressure_file='BBL.tif', output_pore_size_distribution_file="PSD.tif",
                                     output_residual_soil_moisture_file='RSM.tif', output_saturated_soil_moisture_file='SSM.tif',
                                      output_ksat_rawls_file='ksat_rawls.tif',output_ksat_hz_file='ksat_hz.tif',
                                     save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)


        if not self._is_file_name_valid(output_dth1_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth1_raster))
        if not self._is_file_name_valid(output_dth2_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth2_raster))
        if not self._is_file_name_valid(output_psif_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_psif_raster))
        if not self._is_file_name_valid(output_sd_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_sd_raster))


        if not self._is_file_name_valid(output_bubbling_pressure_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_bubbling_pressure_file))
        if not self._is_file_name_valid(output_pore_size_distribution_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_pore_size_distribution_file))
        if not self._is_file_name_valid(output_residual_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_residual_soil_moisture_file))
        if not self._is_file_name_valid(output_saturated_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_saturated_soil_moisture_file))
        if not self._is_file_name_valid(output_ksat_rawls_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_ksat_rawls_file))

        url = self._get_dataservice_specific_url(service_name='downloadsoildataforpytopkapi3')
        payload = {'Watershed_Raster':input_watershed_raster_url_path,
                       'output_dth1_file': output_dth1_raster,'output_dth2_file': output_dth2_raster, 'output_psif_file': output_psif_raster,
                       'output_sd_file': output_sd_raster,
                   'output_bubbling_pressure_file': output_bubbling_pressure_file, 'output_pore_size_distribution_file': output_pore_size_distribution_file,
                   'output_residual_soil_moisture_file': output_residual_soil_moisture_file, 'output_saturated_soil_moisture_file': output_saturated_soil_moisture_file,
                   'output_ksat_rawls_file':output_ksat_rawls_file, 'output_ksat_hz_file':output_ksat_hz_file,
                   }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def downloadsoildataforpytopkapi4(self,input_watershed_raster_url_path,output_dth1_raster='dth1.tif',
                     output_dth2_raster='dth2.tif',output_psif_raster='psif.tif',output_sd_raster='sd.tif',
                                     output_bubbling_pressure_file='BBL.tif', output_pore_size_distribution_file="PSD.tif",
                                     output_residual_soil_moisture_file='RSM.tif', output_saturated_soil_moisture_file='SSM.tif',

                                      output_ksat_LUT_file='ksat_LUT.tif',
                                      output_ksat_ssurgo_wtd_file='ksat_ssurgo_wtd.tif',
                                      output_ksat_ssurgo_min_file='ksat_ssurgo_min.tif',
                                      output_hydrogrp_file='hydrogrp.tif',

                                     save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)


        if not self._is_file_name_valid(output_dth1_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth1_raster))
        if not self._is_file_name_valid(output_dth2_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_dth2_raster))
        if not self._is_file_name_valid(output_psif_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_psif_raster))
        if not self._is_file_name_valid(output_sd_raster, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_sd_raster))


        if not self._is_file_name_valid(output_bubbling_pressure_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_bubbling_pressure_file))
        if not self._is_file_name_valid(output_pore_size_distribution_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_pore_size_distribution_file))
        if not self._is_file_name_valid(output_residual_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_residual_soil_moisture_file))
        if not self._is_file_name_valid(output_saturated_soil_moisture_file, ext='.tif'):
            raise HydroDSArgumentException("{file_name} is not a valid raster file name".format(file_name=output_saturated_soil_moisture_file))


        url = self._get_dataservice_specific_url(service_name='downloadsoildataforpytopkapi4')
        payload = {'Watershed_Raster':input_watershed_raster_url_path,
                       'output_dth1_file': output_dth1_raster,'output_dth2_file': output_dth2_raster, 'output_psif_file': output_psif_raster,
                       'output_sd_file': output_sd_raster,
                   'output_bubbling_pressure_file': output_bubbling_pressure_file, 'output_pore_size_distribution_file': output_pore_size_distribution_file,
                   'output_residual_soil_moisture_file': output_residual_soil_moisture_file, 'output_saturated_soil_moisture_file': output_saturated_soil_moisture_file,
                   'output_ksat_LUT_file':output_ksat_LUT_file,
                   'output_ksat_ssurgo_wtd_file':output_ksat_ssurgo_wtd_file,
                   'output_ksat_ssurgo_min_file': output_ksat_ssurgo_min_file,
                   'output_hydrogrp_file': output_hydrogrp_file,
                   }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def downloadsoildataforpytopkapi5(self,input_watershed_raster_url_path, save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)



        url = self._get_dataservice_specific_url(service_name='downloadsoildataforpytopkapi5')
        payload = {'Watershed_Raster':input_watershed_raster_url_path
                   }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def abstractclimatedata(self, input_raster, startDate, endDate, cell_size=None,
                            output_vp_fname='output_vp.nc',
                            output_tmin_fname='output_tmin.nc',
                            output_tmax_fname='output_tmax.nc',
                            output_srad_fname='output_srad.nc',
                            output_prcp_fname='output_prcp.nc',
                            save_as=None):

        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('abstractclimatedata')
        payload = {
            'input_raster':input_raster,
            'startDate': startDate.replace("-",'/'),
            'endDate': endDate.replace("-",'/'),
            'cell_size':cell_size,

            'output_vp_fname': output_vp_fname,
            'output_tmin_fname': output_tmin_fname,
            'output_tmax_fname': output_tmax_fname,
            'output_srad_fname': output_srad_fname,
            'output_prcp_fname': output_prcp_fname,
        }



        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def calculaterainETfromdaymet(self, input_raster,input_dem, startDate, endDate, cell_size=None,
                                  output_et_reference_fname='output_et.nc', output_rain_fname='output_ppt.nc',
                                  save_as=None):
        # date format: mm/dd/yyyy or mm-dd-yyyy
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('calculaterainETfromdaymet')
        payload = {
            'input_raster':input_raster,
            'input_dem':input_dem,
            'startDate': startDate.replace("-",'/'),
            'endDate': endDate.replace("-",'/'),
            'cell_size':cell_size,

            'output_et_reference_fname': output_et_reference_fname,
            'output_rain_fname': output_rain_fname,
        }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def changetimestepofforcingnetcdf(self, input_netcdf, time_interval_in_hr=6,
                                  output_et_reference_fname='output_et.nc', output_rain_fname='output_ppt.nc',
                                  save_as=None):
        # date format: mm/dd/yyyy or mm-dd-yyyy
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('changetimestepofforcingnetcdf')
        payload = {
            'input_netcdf':input_netcdf,
            'time_interval_in_hr':time_interval_in_hr,

            'output_et_reference_fname': output_et_reference_fname,
            'output_rain_fname': output_rain_fname,
        }

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    def bboxfromtiff(self, input_raster, output_json='responseJSON.txt', save_as=None):
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('bboxfromtiff')
        payload = {"input_raster": input_raster, 'output_json':output_json}

        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def outletxyfromshp(self, input_shp, output_json='responseJSON.txt', save_as=None):
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('outletxyfromshp')
        payload = {"input_shp": input_shp, 'output_json':output_json}
        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def bboxfromshp(self, input_shp, output_json='responseJSON.txt', save_as=None):
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('bboxfromshp')
        payload = {"input_shp": input_shp, 'output_json':output_json}
        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)


    def downloadgeospatialandforcingfiles(self, inputs_dictionary_json,download_request='geospatial',
                                          output_zipfile='output.zip',output_response_txt='metadata.txt', save_as=None):
        if save_as:
            self._validate_file_save_as(save_as)

        url = self._get_dataservice_specific_url('downloadgeospatialandforcingfiles')
        payload = {"inputs_dictionary_json": inputs_dictionary_json,
                   'download_request': download_request,
                   'output_zipfile':output_zipfile,
                   'output_response_txt': output_response_txt
                   }
        response = self._make_data_service_request(url=url, params=payload)
        return self._process_dataservice_response(response, save_as)

    ##################################END OF TOPKAPI FUNCTIONS ################################



    def _validate_resample_input(self, resample):
        allowed_options = ('near', 'bilinear', 'cubic', 'cubicspline', 'lanczos', 'average', 'mode', 'max', 'min',
                           'med', 'q1', 'q3')
        if resample not in allowed_options:
            raise HydroDSArgumentException("{rsample} is not a valid GDAL resampling method".format(resample=resample))

    def _validate_boundary_box(self, bottom, left, right, top):
        if not isinstance(left, float):
            raise HydroDSArgumentException("left value must be a decimal number")
        if not isinstance(top, float):
            raise HydroDSArgumentException("top value must be a decimal number")
        if not isinstance(right, float):
            raise HydroDSArgumentException("right value must be a decimal number")
        if not isinstance(bottom, float):
            raise HydroDSArgumentException("bottom value must be a decimal number")

    def _make_data_service_request(self, url, http_method='GET', params=None, data=None, files=None):
        if http_method == 'GET':
            return self._requests.get(url, params=params, data=data, auth=self._hg_auth)
        elif http_method == 'DELETE':
            return self._requests.delete(url, params=params, data=data, auth=self._hg_auth)
        elif http_method == 'POST':
            return self._requests.post(url, params=params, data=data, files=files, auth=self._hg_auth)
        else:
            raise Exception("%s http method is not supported for the HydroDS API." % http_method)

    def _get_dataservice_specific_url(self, service_name):
        return "{base_url}/{service_name}".format(base_url=self._dataservice_base_url, service_name=service_name)

    def _process_dataservice_response(self, response, save_as=None):
        if response.status_code != requests.codes.ok:
            err_message = response.reason + " " + response.content
            if response.status_code == 400:
                raise HydroDSBadRequestException("HydroDS Service Error. {response_err}".format(response_err=err_message))
            elif response.status_code == 401:
                raise HydroDSNotAuthenticatedException("HydroDS Service Error. {response_err}".format(response_err=err_message))
            elif response.status_code == 403:
                raise HydroDSNotAuthorizedException("HydroDS Service Error. {response_err}".format(response_err=err_message))
            elif response.status_code == 404:
                raise HydroDSNotFoundException("HydroDS Service Error. {response_err}".format(response_err=err_message))
            elif response.status_code == 500:
                raise HydroDSServerException("HydroDS Service Error. {response_err}".format(response_err=err_message))
            else:
                raise HydroDSException("HydroDS Service Error. {response_err}".format(response_err=err_message))

        response_dict = response.json()
        if response_dict['success']:
            if save_as:
                if len(response_dict['data']) != 1:
                    raise ValueError("Multiple output files found. Can't download multiple files.")
                file_url = list(response_dict['data'].values())[0]
                self.download_file(file_url, save_as)
            return response_dict['data']
        else:
            self._raise_service_error(response_dict['error'])

    def _process_service_response(self, response, service_name, save_as=None, strip_zip=True):
        if response.status_code != requests.codes.ok:
            raise Exception("Error: HydroGate connection error.")

        response_dict = json.loads(response.content)
        if response_dict['ret'] == 'success':
            file_url = response_dict['message']
            service_req = ServiceRequest(service_name=service_name, service_id_name='',
                                         service_id_value='', service_status='success', file_path=file_url)

            _ServiceLog.add(service_req)
            self.save_service_call_history()
            if save_as:
                # get rid of the .zip part of the url
                if strip_zip:
                    file_url = file_url[:-4]
                self.download_file(file_url, save_as)

            return service_req
        else:
            self._raise_service_error(response_dict['message'])

    def _raise_service_error(self, message):
        raise HydroDSException("Error:%s" % message)

    def save_service_call_history(self):
        _ServiceLog.save()

    def clear_service_log(self):
        _ServiceLog.delete_all()

    def _is_file_name_valid(self, file_name, ext=None):
        try:
            name_part, ext_part = os.path.splitext(file_name)
            if len(name_part) == 0 or len(ext_part) < 2:
                return False

            if ext:
                if ext != ext_part:
                    return False

            ext_part = ext_part[1:]
            for c in ext_part:
                if not c.isalpha():
                    return False
            if not name_part[0].isalpha():
                return False
            for c in name_part[1:]:
                if not c.isalnum() and c not in ['-', '_']:
                    return False
        except:
            return False
        return True

    def _validate_file_save_as(self, save_as, file_ext=None):
        save_file_dir = os.path.dirname(save_as)
        if not os.path.exists(save_file_dir):
            raise HydroDSArgumentException("Specified file path (%s) to save does not exist." % save_file_dir)

        if not os.access(save_file_dir, os.W_OK):
            raise HydroDSArgumentException("You do not have write permissions to directory '{0}'.".format(save_file_dir))

        file_name = os.path.basename(save_as)
        if not self._is_file_name_valid(file_name):
            raise HydroDSArgumentException("{file_name} is not a valid file name for saving the output "
                                           "file.".format(file_name=file_name))

        if file_ext:
            file_extension = os.path.splitext(save_as)[1]
            if file_extension != file_ext:
                raise HydroDSArgumentException("Invalid save as file type:{file_extension}. File type must "
                                               "be:{file_ext}".format(file_extension=file_extension, file_ext=file_ext))

    def _check_user_irods_authentication(self):
        if not self._user_irods_authenticated:
            raise Exception("You first need to get authenticated to iRODS.")

    def _check_user_hpc_authentication(self):
        if not self._user_hg_authenticated:
            raise Exception("You first need to get authenticated to HPC.")

    def _get_file_name_from_url_file_path(self, url_file_path):
        # given the file url path: "http://129.123.41.158:8080/dem/user2623623514710145932.txt.zip"
        # we will be returning: user2623623514710145932.txt
        file_name = url_file_path.split("/")[-1][:-4]
        return file_name


class _ServiceLog(object):
    _service_requests = []
    _pickle_file_name = r'hg_service_log.pkl'

    @classmethod
    def add(cls, service_request):
        if isinstance(service_request, ServiceRequest):
            cls._service_requests.append(service_request)
        else:
            raise Exception("Internal Error: Only an object of type 'ServiceRequest' can be added to the log.")

    @classmethod
    def remove(cls):
        pass

    @classmethod
    def delete_all(cls):
        cls._service_requests = []
        if os.path.isfile(cls._pickle_file_name):
            os.remove(cls._pickle_file_name)

    @classmethod
    def load(cls):
        if len(cls._service_requests) == 0:
            if os.path.isfile(cls._pickle_file_name):
                with open(cls._pickle_file_name, "rb") as f:
                    cls._service_requests = pickle.load(f)

    @classmethod
    def save(cls):
        if len(cls._service_requests) > 0:
            with open(cls._pickle_file_name, "wb") as f:
                pickle.dump(cls._service_requests, f)
        elif os.path.isfile(cls._pickle_file_name):
            os.remove(cls._pickle_file_name)

    @classmethod
    def print_log(cls, order='first', count=None):
        if len(cls._service_requests) == 0:
            return

        if order == 'last':
            # reverse all items in the list
            service_requests = cls._service_requests[::-1]
        else:
            service_requests = cls._service_requests

        if count:
            try:
                count = int(count)
            except:
                raise ValueError("Count must be an integer value.")
            if count > len(cls._service_requests):
                count = len(cls._service_requests)
        else:
            count = len(cls._service_requests)

        service_requests = service_requests[0:count]
        for req in service_requests:
            print(req.to_json())

    @classmethod
    def get_most_recent_request(cls, service_name=None, service_id_name=None, service_id_value=None):
        if len(cls._service_requests) == 0:
            return None

        if not service_name and not service_id_name:
            return cls._service_requests[-1]
        else:
            reversed_list = reversed(cls._service_requests)
            for item in reversed_list:
                selected_item = None
                if service_name:
                    if item.service_name == service_name:
                       selected_item = item
                if service_id_name:
                    if item.service_id_name == service_id_name:
                        if service_id_value:
                            if item.service_id_value == service_id_value:
                                selected_item = item
                            else:
                                selected_item = None
                        else:
                            selected_item = item
                    else:
                        selected_item = None

                if selected_item:
                    return selected_item

            return None


class ServiceRequest(object):
    def __init__(self, service_name, service_id_name, service_id_value, service_status, file_path=None, request_time=None):
        self.service_name = service_name            # e.g. upload_package
        self.service_id_name = service_id_name      # e.g package_id
        self.service_id_value = service_id_value    # e.g. 109879ghy67890
        self.service_status = service_status        # e.g. uploading
        self.file_path = file_path
        if request_time:
            self.request_time = request_time        # e.g. 10/6/2014 10:00:05
        else:
            self.request_time = datetime.datetime.now()

    def to_json(self):
        object_data = {}
        object_data['Service name'] = self.service_name
        object_data['Service ID name'] = self.service_id_name
        object_data['Service ID value'] = self.service_id_value
        object_data['Service status'] = self.service_status
        object_data['Output file path'] = self.file_path
        object_data['Request time'] = str(self.request_time)
        return json.dumps(object_data, indent=4)