# AllPowers charge controller

It uses the https://github.com/jolle22/hoymiles-wifi-micropython library, to get data from the hoymiles DTU.
When the hoymiles DTU reports a certain energy production, a relay connected to PIN 5 will be turned on.
In my home, this relay is connected to a power outlet, that may charge power-stations, power-banks or phones.

I do hope this helps somebody.