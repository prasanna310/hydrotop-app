$(document).ready(function() {
    $("#sim_list").bind('click', ShowHideAdditionalTabs);

});



function ShowHideAdditionalTabs() {
    document.getElementById('id_1').innerHTML = document.getElementById('simulation_names_list').value;

    document.getElementById('id_1').innerHTML = document.getElementById('calibration_list').value;


//    if (model_engine=='TOPNET') {
//        // $("#topnet_input").show();  //only this is required for jQuery!
//        document.getElementById("topnet_input").style.display = "block";
//        document.getElementById("download_input").style.display = "none";
//        document.getElementById("topkapi_initials").style.display = "none";
//    }


}























