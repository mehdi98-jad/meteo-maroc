CREATE TABLE weather_observations (
    city VARCHAR(100) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(5,2),
    humidity_pct SMALLINT,
    precipitation_mm NUMERIC(8,2),
    wind_speed_kmh NUMERIC(7,2),

    CONSTRAINT pk_weather_observations
        PRIMARY KEY (city, observed_at),

    CONSTRAINT chk_humidity
        CHECK (humidity_pct BETWEEN 0 AND 100),

    CONSTRAINT chk_precipitation
        CHECK (precipitation_mm >= 0),

    CONSTRAINT chk_wind_speed
        CHECK (wind_speed_kmh >= 0)
);