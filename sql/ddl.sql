/* EMS Data Warehouse Schema 
*/

-- 0. Staging Layer (Managed by Python, but defined here for documentation)
IF OBJECT_ID('STG_EMS_INCIDENTS', 'U') IS NOT NULL DROP TABLE STG_EMS_INCIDENTS;

-- 1. Dimension Layer
IF OBJECT_ID('Fact_EMS_Incidents', 'U') IS NOT NULL DROP TABLE Fact_EMS_Incidents;
IF OBJECT_ID('Dim_Location', 'U') IS NOT NULL DROP TABLE Dim_Location;
IF OBJECT_ID('Dim_Provider', 'U') IS NOT NULL DROP TABLE Dim_Provider;
IF OBJECT_ID('ERR_Quarantine', 'U') IS NOT NULL DROP TABLE ERR_Quarantine;

CREATE TABLE Dim_Location (
    LocationKey INT IDENTITY(1,1) PRIMARY KEY,
    CountyName NVARCHAR(255),
    DestinationType NVARCHAR(255),
    UNIQUE (CountyName, DestinationType)
);

CREATE TABLE Dim_Provider (
    ProviderKey INT IDENTITY(1,1) PRIMARY KEY,
    Structure NVARCHAR(255),
    ServiceType NVARCHAR(255),
    ServiceLevel NVARCHAR(255),
    UNIQUE (Structure, ServiceType, ServiceLevel)
);

-- 2. Fact Layer
CREATE TABLE Fact_EMS_Incidents (
    IncidentID INT PRIMARY KEY,
    IncidentTimestamp DATETIME,
    ToSceneMins FLOAT,
    IsInjury BIT,
    LocationKey INT REFERENCES Dim_Location(LocationKey),
    ProviderKey INT REFERENCES Dim_Provider(ProviderKey),
    LoadTimestamp DATETIME DEFAULT GETDATE()
);

-- 3. Error Layer
CREATE TABLE ERR_Quarantine (
    RecordID NVARCHAR(100),
    ErrorReason NVARCHAR(MAX),
    RawData NVARCHAR(MAX),
    LoadTimestamp DATETIME DEFAULT GETDATE(),
    ErrorCategory NVARCHAR(100)
);