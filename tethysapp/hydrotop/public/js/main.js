function showMap() {
     var map = new google.maps.Map(document.getElementById('mymap'), {
     zoom: 9,
     center: {lat: 42, lng: -111.3}
      });

//            var script = document.createElement("script");
//            script.src = "wshed_with_var.geojson";
//            document.getElementsByTagName("head")[0].appendChild(script);
}


window.geojson_callback = function(results) {
         var map = new google.maps.Map(document.getElementById('mymap'), {
         zoom: 9,
         center: {lat: 42, lng: -111.3}
          });

        map.data.addGeoJson(results);
        if (results.features.length >1) {
            alert("Select feature class that contains just the one feature.")
            // :TODO make sure the file is ignored
        } else {

            var coords = results.features[0].geometry.coordinates[0];
            // :todo Make sure to see all the geojson. Because this is only valid for geographic CS
            var xmin = 180.0;
            var xmax = -180.0;
            var ymin = 90.0;
            var ymax = -90.0;
            for (var i = 0; i < coords.length; i++) {

//                    var coords = results.features[i].geometry.coordinates;
//                    var latLng = new google.maps.LatLng(coords[1], coords[0]);
                var x = coords[i][0];
                var y = coords[i][1];
                if (x < xmin) {xmin = x;}
                if (x > xmax) { xmax = x;}
                if (y < ymin) { ymin = y;}
                if (y > ymax) {ymax = y;}

            }
        }
        // Manage extent of the map

        document.getElementById('test_para').innerHTML = xmin.toString() + xmax.toString() + ymin.toString() + ymax.toString() ;

}


function loadFileAsText()
{

    var fileToLoad = document.getElementById("watershed_geojson").files[0]; //this could be outlet_geojson too

    var fileReader = new FileReader();
    fileReader.readAsText(fileToLoad, "UTF-8");

    fileReader.onload = function(fileLoadedEvent)
    {
        var textFromFileLoaded = fileLoadedEvent.target.result;
        window.geojson_callback(JSON.parse(textFromFileLoaded))
    };

}