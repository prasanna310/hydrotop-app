# Put your persistent store models in this file

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, Text, Date,  ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import relationship

from .app import Hydrotop

# DB Engine, sessionmaker and base
engine = Hydrotop.get_persistent_store_engine('hydrotop_db')
SessionMaker = sessionmaker(bind=engine)
Base = declarative_base()


class model_inputs_table(Base):
    __tablename__ = 'model_inputs_table'

    # Columns
    id = Column(Integer, primary_key=True)
    children = relationship("model_calibration_table")

    user_name = Column(Text)
    simulation_name = Column(Text)
    hs_resource_id = Column(Text)
    simulation_start_date = Column(Date)
    simulation_end_date = Column(Date)
    USGS_gage = Column(Integer)

    outlet_x = Column(Float)
    outlet_y = Column(Float)
    box_topY = Column(Float)
    box_bottomY = Column(Float)
    box_rightX = Column(Float)
    box_leftX = Column(Float)

    model_engine = Column(Text)
    other_model_parameters = Column(Text)
    # timeseries_source =  Column(Text)
    # threshold = Column(Float)
    # cell_size = Column(Float)
    # timestep = Column(Float)

    remarks = Column(Text)
    user_option = Column(Text)




    def __init__(self, user_name, simulation_name,hs_resource_id,simulation_start_date,simulation_end_date,USGS_gage,
                 outlet_x,outlet_y, box_topY,box_bottomY, box_rightX,box_leftX,
                 model_engine,other_model_parameters, remarks, user_option  ):
        self.user_name = user_name
        self.simulation_name = simulation_name
        self.hs_resource_id = hs_resource_id
        self.simulation_start_date_picker = simulation_start_date
        self.simulation_end_date_picker = simulation_end_date
        self.USGS_gage = USGS_gage

        self.outlet_x = outlet_x
        self.outlet_y = outlet_y
        self.box_topY = box_topY
        self.box_bottomY = box_bottomY
        self.box_rightX = box_rightX
        self.box_leftX = box_leftX

        self.model_engine = model_engine
        self.other_model_parameters = other_model_parameters
        # self.cell_size = cell_size
        # self.timestep = timestep
        # self.threshold = threshold
        # self.timeseries_source = timeseries_source

        self.remarks = remarks
        self.user_option = user_option


class model_calibration_table(Base):

    __tablename__ = 'model_calibration_table'

    # Columns
    id = Column(Integer, primary_key=True)
    input_table_id = Column(Integer, ForeignKey('model_inputs_table.id'),  nullable=False)

    numeric_parameters = Column(Text)
    calibration_parameters = Column(Text)

    # fac_L_form = Column(Float)
    # fac_Ks_form = Column(Float)
    # fac_n_o_form = Column(Float)
    # fac_n_c_form = Column(Float)
    # fac_th_s_form = Column(Float)
    #
    # pvs_t0_form = Column(Float)
    # vo_t0_form = Column(Float)
    # qc_t0_form = Column(Float)
    # kc_form = Column(Float)


    def __init__(self,numeric_parameters, calibration_parameters, input_table_id ):

        self.numeric_parameters = numeric_parameters
        self.calibration_parameters = calibration_parameters
        self.input_table_id = input_table_id

        # self.fac_Ks_form = fac_Ks_form
        # self.fac_n_o_form = fac_n_o_form
        # self.fac_n_c_form = fac_n_c_form
        # self.fac_th_s_form = fac_th_s_form
        #
        # self.pvs_t0_form = pvs_t0_form
        # self.vo_t0_form = vo_t0_form
        # self.qc_t0_form = qc_t0_form
        # self.kc_form = kc_form


class model_result_table(Base):

    __tablename__ = 'model_result_table'

    # Columns
    id = Column(Integer, primary_key=True)
    model_calibration_id = Column(Integer, ForeignKey('model_calibration_table.id'),  nullable=False)

    datetime = Column(DateTime)
    # UTC_offset = Column(DateTime)
    simulated_discharge = Column(Float)
    observed_discharge = Column(Float)


    def __init__(self,date_time, simulated_discharge, observed_discharge, model_calibration_id ,UTC_offset=None ):
        """
        Constructor for a gage
        """
        self.date_time = date_time
        # self.UTC_offset = UTC_offset
        self.simulated_discharge = simulated_discharge
        self.observed_discharge = observed_discharge
        self.model_calibration_id = model_calibration_id



# :TODO metadata table for each of the three tables
