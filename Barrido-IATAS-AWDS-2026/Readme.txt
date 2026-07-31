- La aplicación extrae y filtra los Awds y IAtas nuevas de un periodo especificado y sigue el siguiente flujo :
El flujo de trabajo seria el siguiente: 


 - Se ex
Carpetas: 
	- AWDBarridoWizard es la carpeta donde almacenas manualmente el resultado del Barrido resultado del
		AWD_Mapeo_interfaz.exe
	- AWDExtraidoSQL: Es la carpeta donde se almacena el resultado de SQLExtraerAWD.py es decir
	el archivo csv con los AWD del periodo establecido.
	- BD_AWDs: Es donde se almacena las bases de datos del drive. O las que se subiran al drive con
	los nuevos AWD ya mapeados.
	- Codigos: donde se almacenan los scripts en python.
	-ConsultasSQL: Donde se almacena el archivo de consulta para extraer los AWD del sql.
	- NuevosAWDFiltrados: ahi se almacenan los archivos csv con los AWD nuevos resultantes de comparar
	los extraidos del SQL y de la BD_ADWs para que posteriormente ese archivo se le pase al wizard.