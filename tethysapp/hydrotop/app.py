from tethys_sdk.base import TethysAppBase, url_map_maker
from tethys_sdk.stores import PersistentStore


class Hydrotop(TethysAppBase):
    """
    Tethys app class for HydroTop.
    """

    name = 'HydroTop'
    index = 'hydrotop:home'
    icon = 'hydrotop/images/icon13.png'
    package = 'hydrotop'
    root_url = 'hydrotop'
    color = 'blue'
    description = 'Model instance for TOPKAPI, model input for TOPNET, and downloading hydrologic ataset'
    tags = '"USU"' #"Hydrology", "topkapi", "topnet", "TauDEM",
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


                    UrlMap(name='visualize_shp',
                           url='hydrotop/visualize_shp',
                           controller='hydrotop.controllers.visualize_shp'),

                    # /hydrotop/test2
                    UrlMap(name='tables',
                           url='hydrotop/tables',
                           controller='hydrotop.controllers.tables'),

                    UrlMap(name='model_input0',
                           url='hydrotop/model_input0',
                           controller='hydrotop.controllers.model_input0'),

                    UrlMap(name='model_input1',
                           url='hydrotop/model_input1',
                           controller='hydrotop.controllers.model_input1'),
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