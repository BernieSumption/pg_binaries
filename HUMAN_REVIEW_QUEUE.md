# Human review queue

## Address Standardizer US data redistribution

The [Address Standardizer project](https://github.com/postgis/address_standardizer) provides `address_standardizer` and `address_standardizer_data_us`. Its source says the latter includes city-name files derived from USPS data. The repository licence covers project code, but the reviewed upstream material does not establish redistribution rights for those data files. [USPS AIS resources](https://postalpro.usps.com/resources/address-quality/ais-viewer) refer to a separate data licence; its applicability to these particular files is unresolved.

The functional specification prohibits including a project when merely creating its extension and using its objects in schema DDL depends on data that cannot be redistributed. Please determine whether the US data in this extension may be freely redistributed in public archives, or provide a source that establishes the rights. Until then, do not advertise either SQL extension from this project. Other extension and PostgreSQL work can proceed.
