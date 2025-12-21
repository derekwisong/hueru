# hueru

## Details


To control the lightstrip, you will send an HTTP PUT request to the 
following endpoint:

`http://<bridge ip address>/api/<username>/lights/<light-ID>/state`

Replace <bridge ip address>, <username>, and <light-ID> with your
specific values. The <light-ID> is the numerical ID assigned to your
lightstrip, which you can find by performing a GET request to:

`/api/<username>/lights`

The Hue API accepts color information in a few different formats.
You can choose the method that best suits your needs: 

XY Color Coordinates: This is the most precise method. The values
are floats between 0.0 and 1.0, representing coordinates on the CIE
color space diagram.

- Example (Red): `{"on": true, "xy": [0.6866, 0.3107], "bri": 254}`
- Example (Green): `{"on": true, "xy": [0.1862, 0.6878], "bri": 254}`
- Hue, Saturation, and Brightness (HSB):
  - Hue values range from 0 to 65535, and saturation/brightness values
    from 0 to 254.
  - Example (Blue): `{"on": true, "hue": 44076, "sat": 254, "bri": 56}`
- Color Temperature (CT):
  - Used for shades of white, specified in Mired values (153-500, where 
    lower is warmer and higher is colder).
  - Example (Warm White): `{"on": true, "ct": 400, "bri": 200}`

## Example using cURL

```bash
curl -X PUT -d '{"on": true, "xy": [0.6866, 0.3107], "bri": 254}' http://<bridge ip address>/api/<username>/lights/1/state
```

