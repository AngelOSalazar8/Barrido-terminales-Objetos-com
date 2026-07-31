SELECT 
      [Primary_Awd_Org_Id]
FROM [dbAreaCorp].[dbo].[Reservaciones]
WHERE Booking_Date >= '2025-03-15'
ORDER BY Booking_Date DESC


-- La fecha es de la ultima vez que se corrio el barrido entonces 
-- extraemos los awd desde esa fecha hasta hoy