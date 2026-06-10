# Inventory update event — published by Adapter when stock changes
string sku
float64 available
float64 reserved
string location
string source           # warehouse_sync | mission_consume | mission_produce | manual_load
builtin_interfaces/Time stamp
