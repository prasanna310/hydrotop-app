from .model import engine, SessionMaker, Base, model_inputs_table

# this function is called for the first time a db is created, with first_time=True argument
# at this time, this should create all the tables, and if there is initial data, this should create those too
# this function can be initiated by typing in shell:   $tethys syncstores hydrotop -f # f is for argument first_time=True
def init_hydrotop_db(first_time, username='prasanna'):
    """
    An example persistent store initializer function
    """
    # Create tables
    Base.metadata.create_all(engine)

    if first_time:
        # Make session
        session = SessionMaker()

        # To add value to the db for the first time
        sample_run = model_inputs_table(user_name= username,
                                   simulation_name="Sample_Simulation",
                                   hs_resource_id="10a357a5277a4792b0d901442ed9ff1d",
                                   simulation_start_date='01/01/2010',
                                   simulation_end_date='01/01/2011',
                                   USGS_gage="10172200",
                                   outlet_y=" 41.74025",
                                   outlet_x="-111.7915",
                                   box_topY="41.85239",
                                   box_bottomY="41.6938188",
                                   box_rightX="-111.887299",
                                   box_leftX="-111.661999",
                                   model_engine = "TOPKAPI",

                                   other_model_parameters= "X"+"__"+ "1000" + "__"+ "100" + "__"+ "3600",
                                   remarks='success',
                                   user_option='download'
                                       )
        session.add(sample_run)
        session.commit()




