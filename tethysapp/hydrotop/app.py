from tethys_sdk.base import TethysAppBase, url_map_maker
from tethys_sdk.stores import PersistentStore


class Hydrotop(TethysAppBase):
    """
    Tethys app class for HydroTop.
    """

    name = 'HydroTop'
    index = 'hydrotop:home'
    icon = 'hydrotop/images/icon.gif'
    package = 'hydrotop'
    root_url = 'hydrotop'
    color = '#e67e22'
    description = 'Model instance for TOPKAPI, model input for TOPNET, and downloading hydrologic ataset'
    tags = '"Hydrology", "topkapi", "topnet", "terrain analysis", "TauDEM", "watershed delineation", "hydrotop", "modeling", "reference ET", "evapotranspiration", "daymet", "climate files", "forcing files", "ssurgo", "soil files", "saturated hydraulic conductivity", "porosity", "residual soil moisture content", "gssurgo", "terrain analysis", "bubbling pressure", "pore size distribution","USU", "UWRL", "Utah State University", "hydroshare"'
    enable_feedback = False
    feedback_emails = []

        
    def url_maps(self):
        """
        Add controllers
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (UrlMap(name='home',
                           url='hydrotop',
                           controller='hydrotop.controllers.model_input'),

                    UrlMap(name='model_input',
                           url=r'hydrotop/model_input',
                           controller='hydrotop.controllers.model_input'),

                    UrlMap(name='model_run',
                           url='hydrotop/model_run',
                           controller='hydrotop.controllers.model_run'),

                    # /hydrotop/model-input2
                    UrlMap(name='model_input2',
                           url='hydrotop/model_input2',
                           controller='hydrotop.controllers.model_input2'),

                    UrlMap(name='visualize_shp',
                           url='hydrotop/visualize_shp',
                           controller='hydrotop.controllers.visualize_shp'),

                    # # /hydrotop/test2
                    # UrlMap(name='test2',
                    #        url='hydrotop/test2',
                    #        controller='hydrotop.controllers.test2'),



                    UrlMap(name='model_input0',
                           url='hydrotop/model_input0',
                           controller='hydrotop.controllers.model_input0'),
                    #
                    # UrlMap(name='test3',
                    #        url='hydrotop/test3',
                    #        controller='hydrotop.controllers.test3'),
        )

        return url_maps
    
    def persistent_stores(self):
        """
        Add one or more persistent stores
        """
        # 'init_stores:init_stream_gage_db' --> format same as abc.xyz:function_name
        stores = (PersistentStore(name='hydrotop_db',
                                  initializer='hydrotop.init_stores.init_hydrotop_db',
                                  spatial=True
                                  ),
                  )

        return stores