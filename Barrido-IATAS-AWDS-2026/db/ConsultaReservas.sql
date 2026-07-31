SELECT 
    [ReservationId] ,[Booking_Date] ,[ATC_Iata_Num] 
FROM 
    [dbAreaCorp].[dbo].[Reservaciones] 
where 
    [Booking_Date] >= '2022-11-07'
ORDER BY Booking_Date DESC
-- 2023-11-17 el exe muestra eso.