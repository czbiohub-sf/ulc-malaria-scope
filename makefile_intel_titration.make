VAR := op_Point1  op_Point2 op_Point3 op_Point4 op_Point5 op_Point6 op_Point7 op_Point8 op_Point9 op_Point10

target: $(VAR)

$(VAR):
	python /Users/pranathi.vemuri/czbiohub/ulc-malaria-scope/ulc_mm_package/image_processing/calculate_titration_percentage.py -i /Users/pranathi.vemuri/czbiohub/ulc-malaria-scope/titration_results/$@ titration_data_leica.csv