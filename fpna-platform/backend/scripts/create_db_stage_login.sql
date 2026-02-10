-- Run this script in SQL Server (SSMS or sqlcmd) to create a login and user for DB_STAGE
-- so you can plug it into FPNA Manage Connections and explore tables.

USE [master];
GO

-- Create login (change password in production)
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = N'fpna_stage_reader')
BEGIN
    CREATE LOGIN [fpna_stage_reader] WITH PASSWORD = N'FPNA_Stage_Read_2024!',
        DEFAULT_DATABASE = [DB_STAGE],
        CHECK_EXPIRATION = OFF,
        CHECK_POLICY = ON;
    PRINT 'Login fpna_stage_reader created.';
END
ELSE
    PRINT 'Login fpna_stage_reader already exists.';
GO

USE [DB_STAGE];
GO

-- Create user in DB_STAGE
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'fpna_stage_reader')
BEGIN
    CREATE USER [fpna_stage_reader] FOR LOGIN [fpna_stage_reader];
    PRINT 'User fpna_stage_reader created in DB_STAGE.';
END
ELSE
    PRINT 'User fpna_stage_reader already exists in DB_STAGE.';
GO

-- Grant read metadata (see tables/columns) and read data
GRANT VIEW DEFINITION TO [fpna_stage_reader];
GRANT SELECT ON SCHEMA::dbo TO [fpna_stage_reader];

-- If your tables are in other schemas, grant per schema, e.g.:
-- GRANT SELECT ON SCHEMA::staging TO [fpna_stage_reader];
-- GRANT SELECT ON SCHEMA::dim TO [fpna_stage_reader];

PRINT 'Done. Use in FPNA:';
PRINT '  Host: your_sql_server_host (e.g. localhost or . or 127.0.0.1)';
PRINT '  Port: 1433';
PRINT '  Database: DB_STAGE';
PRINT '  Username: fpna_stage_reader';
PRINT '  Password: FPNA_Stage_Read_2024!';
