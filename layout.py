"""Tata letak form gaya BIG Metadata Editor (13 seksi) yang terikat ke pohon XML ISO 19115-3.

Tanpa Qt. Path memakai nama elemen; nama kelas (mis. CI_Citation) boleh dilewati.
Selektor: name[2] = instans ke-2, name[=nilai] = berisi codeListValue tsb, name[~Kelas] = berisi kelas tsb.
"""
import copy
import json
import os
import re

from . import model
from .model import Field, local, VALUE_TYPES, ENUM_TEXT, MULTILINE

with open(os.path.join(os.path.dirname(__file__), "big_assets.json"), encoding="utf-8") as _fh:
    ASSETS = json.load(_fh)
OPTS, DESC = ASSETS["options"], ASSETS["desc"]


# ------------------------------------------------------------------ DSL spesifikasi
class F:
    """Field. path relatif; akhiran '#0'/'#1' = komponen gml:pos, '/@attr' = atribut. hide=True: sembunyikan bila tak ada."""
    def __init__(self, key, label, path, opts=None, hide=False):
        self.key, self.label, self.path, self.opts, self.hide = key, label, path, opts, hide


class L:
    """Daftar berulang. snips = [(label, nama_snippet)] untuk menu tambah berbasis template."""
    def __init__(self, title, path, items, show_class=False, snips=None):
        self.title, self.path, self.items, self.show_class, self.snips = title, path, items, show_class, snips


class O:
    """Blok opsional: kotak centang yang menyisipkan/menghapus snippet pada XML."""
    def __init__(self, label, path, snippet, items):
        self.label, self.path, self.snippet, self.items = label, path, snippet, items


class G:
    def __init__(self, label):
        self.label = label


class T:
    def __init__(self, label):
        self.label = label


class N:
    def __init__(self, text):
        self.text = text


def CONTACT():
    c = "party/contactInfo/"
    a = c + "address/"
    return [
        F("role", "Peran / Role", "role", "roleOptions"),
        F("organization", "Organisasi", "party/name"),
        F("individual", "Nama Individu", "party/individual/name"),
        F("position", "Posisi / Jabatan", "party/individual/positionName"),
        F("phone", "Telepon", c + "phone[=voice]/number"),
        F("fax", "Fax", c + "phone[=facsimile]/number"),
        F("email", "Email", a + "electronicMailAddress"),
        F("address", "Alamat", a + "deliveryPoint"),
        F("city", "Kota", a + "city"),
        F("province", "Provinsi", a + "administrativeArea"),
        F("postalCode", "Kode Pos", a + "postalCode"),
        F("country", "Negara", a + "country"),
        F("hours", "Jam Layanan", c + "hoursOfService"),
        F("instructions", "Instruksi Kontak", c + "contactInstructions"),
    ]


def ONLINE():
    return [F("url", "Linkage URL", "linkage"), F("protocol", "Protocol", "protocol"),
            F("name", "Nama", "name"), F("description", "Deskripsi", "description"),
            F("function", "Fungsi", "function", "onlineFunctionOptions")]


def BAND():
    return [
        F("authority", "Otoritas Identifier", "name/authority/title"), F("code", "Kode Identifier", "name/code"),
        F("codeSpace", "Code Space", "name/codeSpace"), F("sequenceId", "Sequence ID", "sequenceIdentifier/aName"),
        F("description", "Deskripsi Band", "description"),
        F("maxValue", "Max Value", "maxValue"), F("minValue", "Min Value", "minValue"),
        F("scaleFactor", "Scale Factor", "scaleFactor"), F("bitsPerValue", "Bits Per Value", "bitsPerValue"),
        F("boundMin", "Bound Min (nm)", "boundMin"), F("boundMax", "Bound Max (nm)", "boundMax"),
        F("peakResponse", "Peak Response (nm)", "peakResponse"), F("toneGradation", "Tone Gradation", "toneGradation"),
        L("Elemen Rentang", "rangeElementDescription", [
            F("name", "Nama", "name"), F("definition", "Definisi", "definition"),
            L("Nilai", "rangeElement", [F("value", "Nilai", ".")])]),
    ]


def COVERAGE():
    return [
        F("coverageAttributeDescription", "Deskripsi Atribut", "attributeDescription"),
        F("coverageProcessingLevelCode", "Kode Processing Level", "processingLevelCode/code"),
        F("coverageProcessingLevelDescription", "Deskripsi Processing Level", "processingLevelCode/description"),
        L("Grup Atribut", "attributeGroup", [F("contentType", "Content Type", "contentType"),
                                              L("Band", "attribute", BAND())]),
    ]


def IMAGE():
    return COVERAGE() + [
        F("imageIlluminationElevation", "Illumination Elevation Angle (°)", "illuminationElevationAngle"),
        F("imageIlluminationAzimuth", "Illumination Azimuth Angle (°)", "illuminationAzimuthAngle"),
        F("imageImagingCondition", "Imaging Condition", "imagingCondition"),
        F("imageQualityAuthority", "Otoritas Kualitas Citra", "imageQualityCode/authority/title"),
        F("imageQualityCode", "Kode Kualitas Citra", "imageQualityCode/code"),
        F("imageCloudCoverPercentage", "Cloud Cover (%)", "cloudCoverPercentage"),
        F("imageCompressionGenerationQuantity", "Compression Generation Quantity", "compressionGenerationQuantity"),
        F("imageTriangulationIndicator", "Triangulation Indicator", "triangulationIndicator"),
        F("imageRadiometricCalibration", "Radiometric Calibration Tersedia", "radiometricCalibrationDataAvailability"),
        F("imageCameraCalibration", "Camera Calibration Tersedia", "cameraCalibrationInformationAvailability"),
        F("imageFilmDistortion", "Film Distortion Info Tersedia", "filmDistortionInformationAvailability"),
        F("imageLensDistortion", "Lens Distortion Info Tersedia", "lensDistortionInformationAvailability"),
    ]


def GRID_BASE():
    return [
        F("rasterNumDimensions", "Jumlah Dimensi Spasial", "numberOfDimensions"),
        F("rasterCellGeometry", "Geometri Sel", "cellGeometry"),
        L("Dimensi", "axisDimensionProperties", [
            F("dimName", "Nama Dimensi (row/column)", "dimensionName"),
            F("dimSize", "Ukuran Sel (jumlah)", "dimensionSize"),
            F("dimRes", "Resolusi (meter)", "resolution")]),
        F("rasterTransformationParams", "Parameter Transformasi Tersedia", "transformationParameterAvailability"),
    ]


def GRID():
    return GRID_BASE() + [
        F("rasterCheckPointAvailability", "Check Point Tersedia", "checkPointAvailability"),
        F("rasterCheckPointDescription", "Deskripsi Check Point", "checkPointDescription"),
        F("rasterCornerPoint1Lat", "Corner 1 Lat", "cornerPoints[1]/pos#0"),
        F("rasterCornerPoint1Lon", "Corner 1 Lon", "cornerPoints[1]/pos#1"),
        F("rasterCornerPoint2Lat", "Corner 2 Lat", "cornerPoints[2]/pos#0"),
        F("rasterCornerPoint2Lon", "Corner 2 Lon", "cornerPoints[2]/pos#1"),
        F("rasterCentrePointLat", "Centre Lat", "centrePoint/pos#0"),
        F("rasterCentrePointLon", "Centre Lon", "centrePoint/pos#1"),
        F("rasterPointPixel", "Orientasi Piksel (Point in Pixel)", "pointInPixel"),
        F("rasterTransformationDimensionDescription", "Deskripsi Transformasi Dimensi", "transformationDimensionDescription"),
        L("Mapping", "transformationDimensionMapping", [F("value", "Mapping", ".")]),
    ]


def GEOREF():
    c = "geolocationInformation/"
    return GRID_BASE() + [
        F("controlPointAvailability", "Control Point Tersedia", "controlPointAvailability"),
        F("orientationParameterAvailability", "Parameter Orientasi Tersedia", "orientationParameterAvailability"),
        F("orientationParameterDescription", "Deskripsi Parameter Orientasi", "orientationParameterDescription"),
        F("georeferencedParameters", "Parameter Georeferensi", "georeferencedParameters"),
        F("rasterGCPCollectionId", "Collection ID", c + "collectionIdentification"),
        F("rasterGCPCollectionName", "Nama Collection", c + "collectionName"),
        F("rasterGCPCollectionCRS", "Kode CRS", c + "coordinateReferenceSystem/referenceSystemIdentifier/code"),
        F("rasterGCPCollectionCRSSpace", "CRS Space", c + "coordinateReferenceSystem/referenceSystemIdentifier/codeSpace"),
        L("GCP", c + "gcp", [F("lat", "Latitude", "geographicCoordinates/pos#0"),
                            F("lon", "Longitude", "geographicCoordinates/pos#1"),
                            F("accuracyReport", "Laporan Akurasi", "accuracyReport/result/statement")]),
    ]


def SOURCE():
    return [
        F("description", "Deskripsi Sumber Data", "description"),
        F("spatialResolution", "Resolusi Spasial Sumber (m)", "sourceSpatialResolution/distance"),
        F("referenceSystemCode", "Sistem Referensi Koordinat", "sourceReferenceSystem/referenceSystemIdentifier/code"),
        F("referenceSystemCodeSpace", "Code Space CRS", "sourceReferenceSystem/referenceSystemIdentifier/codeSpace"),
        F("citationTitle", "Judul Sitasi Sumber", "sourceCitation/title"),
        F("citationDate", "Tanggal Sitasi", "sourceCitation/date/date"),
        F("citationDateType", "Tipe Tgl Sitasi", "sourceCitation/date/dateType", "dateTypeOptions"),
        F("metadataTitle", "Judul Metadata Sumber", "sourceMetadata/title"),
        F("scopeLevel", "Scope Level Sumber", "scope/level", "scopeOptions"),
    ]


def STEP():
    return [
        F("description", "Deskripsi Proses", "description"),
        F("rationale", "Alasan / Rasional", "rationale"),
        F("stepDateTime", "Waktu Proses", "stepDateTime"),
        F("processorName", "Pelaksana (Organisasi)", "processor/party/name"),
        F("processorRole", "Peran Pelaksana", "processor/role", "roleOptions"),
        F("referenceTitle", "Referensi Dokumen", "reference/title"),
        F("scopeLevel", "Scope Level Proses", "scope/level", "scopeOptions"),
        O("Informasi Pengolahan (Processing Information)", "processingInformation", "proc_processing", [
            F("processingId", "ID Processing", "identifier/code"),
            F("softwareReference", "Referensi Software", "softwareReference/title"),
            F("documentation", "Dokumentasi (Judul)", "documentation/title"),
            F("procedureDescription", "Deskripsi Prosedur", "procedureDescription"),
            F("runTimeParameters", "Runtime Parameters", "runTimeParameters"),
            F("algorithmTitle", "Judul Algoritma", "algorithm/citation/title"),
            F("algorithmDescription", "Deskripsi Algoritma", "algorithm/description"),
            L("Parameter", "parameter", [
                F("name", "Nama", "name/aName"), F("direction", "Arah (in/out/inOut)", "direction"),
                F("description", "Deskripsi", "description"), F("optionality", "Opsional", "optionality"),
                F("repeatability", "Dapat Berulang", "repeatability"), F("value", "Nilai", "value")],
              snips=[("Parameter", "param")])]),
        O("Laporan Tahap Proses (Process Step Report)", "report", "proc_report", [
            F("reportName", "Nama Laporan", "name"), F("reportDescription", "Deskripsi Laporan", "description"),
            F("reportFileType", "Tipe File Laporan", "fileType")]),
        O("Sumber Masukan Proses (Source)", "source", "proc_source", SOURCE()),
        O("Hasil Keluaran Proses (Output)", "output", "proc_output", SOURCE() + [
            F("outputLEProcessedLevel", "Processed Level Output", "processedLevel/code"),
            F("outputLEGroundResolution", "Ground Resolution Output (m)", "resolution/groundResolution")]),
    ]


def RESULT():
    return [
        F("dateTime", "Tanggal & Waktu Hasil", "dateTime", hide=True),
        F("resultScope", "Scope Hasil (Result Scope)", "resultScope/level", "scopeOptions", hide=True),
        F("specificationTitle", "Judul Spesifikasi", "specification/title", hide=True),
        F("specificationAlternate", "Spesifikasi Alternatif", "specification/alternateTitle", hide=True),
        F("explanation", "Penjelasan Hasil", "explanation", hide=True),
        F("pass", "Pass", "pass", hide=True),
        F("quantitativeValue", "Nilai Kuantitatif", "value", hide=True),
        F("quantitativeUnit", "Unit/Satuan", "valueUnit/name", hide=True),
        F("quantitativeUnitCode", "Kode Unit", "valueUnit/identifier", hide=True),
        F("quantitativeValueType", "Tipe Record Nilai", "valueRecordType", hide=True),
        F("descriptiveStatement", "Pernyataan Deskriptif", "statement", hide=True),
        F("coverageSpatialRepType", "Tipe Representasi Spasial Hasil", "spatialRepresentationType", "spatialRepTypeOptions", hide=True),
        F("coverageResultFileName", "Nama File Hasil", "resultFile/fileName", hide=True),
        F("coverageResultFileSrc", "Path/URL File Hasil", "resultFile/fileName/@src", hide=True),
        F("coverageResultFileTypeName", "Tipe File", "resultFile/fileType", hide=True),
        F("coverageResultFileType", "Tipe MIME File", "resultFile/fileType/@type", hide=True),
        F("coverageResultFileDescription", "Deskripsi File", "resultFile/fileDescription", hide=True),
        F("coverageResultFileFormatTitle", "Format File (Judul)", "resultFile/fileFormat/formatSpecificationCitation/title", hide=True),
        F("coverageResultAmendmentNumber", "Amendment Number", "resultFormat/amendmentNumber", hide=True),
        F("coverageResultFileDecompression", "File Decompression Technique", "resultFormat/fileDecompressionTechnique", hide=True),
        F("coverageResultContentDesc", "Deskripsi Konten Hasil", "resultContentDescription/attributeDescription", hide=True),
        F("coverageResultContentType", "Tipe Konten Hasil", "resultContentDescription/attributeGroup/contentType", hide=True),
    ]


def ACQUISITION():
    r = "acquisitionRequirement/"
    return [
        F("acquisitionScope", "Scope Level Akuisisi", "scope/level", "scopeOptions"),
        G("Persyaratan Akuisisi"),
        F("acquisitionRequirementTitle", "Judul Persyaratan", r + "citation/title"),
        F("acquisitionRequirementId", "ID Persyaratan", r + "identifier/code"),
        F("acquisitionRequirementDate", "Tanggal Persyaratan", r + "citation/date/date"),
        F("acquisitionPriority", "Prioritas", r + "priority"),
        F("acquisitionRequestedDateCollection", "Tgl Koleksi Diminta", r + "requestedDate/requestedDateOfCollection"),
        F("acquisitionLatestAcceptableDate", "Tgl Terakhir Diterima", r + "requestedDate/latestAcceptableDate"),
        F("acquisitionRequestorRole", "Role Requestor", r + "requestor/role", "roleOptions"),
        F("acquisitionRequestorOrg", "Organisasi Requestor", r + "requestor/party/name"),
        F("acquisitionRecipientRole", "Role Recipient", r + "recipient/role", "roleOptions"),
        F("acquisitionRecipientOrg", "Organisasi Recipient", r + "recipient/party/name"),
        F("acquisitionExpiryDate", "Tanggal Kadaluarsa", r + "expiryDate"),
        G("Kondisi Lingkungan"),
        F("acquisitionAvgAirTemp", "Suhu Udara Rata-rata (°C)", "environmentalConditions/averageAirTemperature"),
        F("acquisitionMaxHumidity", "Kelembaban Maks (%)", "environmentalConditions/maxRelativeHumidity"),
        F("acquisitionMaxAltitude", "Ketinggian Maks (m)", "environmentalConditions/maxAltitude"),
        F("acquisitionMeteoConditions", "Kondisi Meteorologi", "environmentalConditions/meterologicalConditions"),
        F("acquisitionSolarAzimuth", "Solar Azimuth (°)", "environmentalConditions/solarAzimuth"),
        F("acquisitionSolarElevation", "Solar Elevation (°)", "environmentalConditions/solarElevation"),
        G("Instrumen"),
        F("instrumentCitationTitle", "Judul Spesifikasi Instrumen", "instrument/citation/title"),
        F("instrumentCitationDate", "Tanggal Spesifikasi", "instrument/citation/date/date"),
        F("instrumentId", "ID Instrumen", "instrument/identifier/code"),
        F("instrumentType", "Tipe Instrumen", "instrument/type"),
        F("instrumentDescription", "Deskripsi Instrumen", "instrument/description"),
        F("instrumentOtherPropertyType", "Tipe Properti Lain", "instrument/otherPropertyType"),
        F("instrumentOtherProperty", "Nilai Properti Lain", "instrument/otherProperty"),
        G("Tujuan Akuisisi"),
        F("objectiveId", "ID Tujuan", "objective/identifier/code"),
        F("objectivePriority", "Prioritas Tujuan", "objective/priority"),
        F("objectiveType", "Tipe Tujuan", "objective/type"),
        F("objectiveFunction", "Fungsi Tujuan", "objective/function"),
        F("objectiveExtentDescription", "Deskripsi Cakupan Tujuan", "objective/extent/description"),
        F("objectiveWest", "Batas Bujur Barat (°)", "objective/extent/geographicElement/westBoundLongitude"),
        F("objectiveEast", "Batas Bujur Timur (°)", "objective/extent/geographicElement/eastBoundLongitude"),
        F("objectiveSouth", "Batas Lintang Selatan (°)", "objective/extent/geographicElement/southBoundLatitude"),
        F("objectiveNorth", "Batas Lintang Utara (°)", "objective/extent/geographicElement/northBoundLatitude"),
        F("objectiveTimeBegin", "Waktu Mulai Cakupan", "objective/extent/temporalElement/extent/beginPosition"),
        F("objectiveTimeEnd", "Waktu Selesai Cakupan", "objective/extent/temporalElement/extent/endPosition"),
        F("eventId", "ID Kejadian (objectiveOccurence)", "objective/objectiveOccurence/identifier/code"),
        F("eventTrigger", "Pemicu Kejadian", "objective/objectiveOccurence/trigger"),
        F("eventContext", "Konteks Kejadian", "objective/objectiveOccurence/context"),
        F("eventSequence", "Urutan Kejadian", "objective/objectiveOccurence/sequence"),
        F("eventTime", "Waktu Kejadian", "objective/objectiveOccurence/time"),
        G("Operasi"),
        F("operationDescription", "Deskripsi Operasi", "operation/description"),
        F("operationCitationTitle", "Judul Dokumen Operasi", "operation/citation/title"),
        F("operationId", "ID Operasi", "operation/identifier/code"),
        F("operationStatus", "Status Operasi", "operation/status", "statusOptions"),
        F("operationType", "Tipe Operasi", "operation/type"),
        F("operationOtherPropertyType", "Tipe Properti Lain", "operation/otherPropertyType"),
        F("operationOtherProperty", "Nilai Properti Lain", "operation/otherProperty"),
        G("Platform"),
        F("platformCitationTitle", "Judul Spesifikasi Platform", "platform/citation/title"),
        F("platformId", "ID Platform", "platform/identifier/code"),
        F("platformDescription", "Deskripsi Platform", "platform/description"),
        F("platformSponsorRole", "Role Sponsor Platform", "platform/sponsor/role", "roleOptions"),
        F("platformSponsorOrg", "Organisasi Sponsor Platform", "platform/sponsor/party/name"),
        F("platformOtherPropertyType", "Tipe Properti Lain", "platform/otherPropertyType"),
        F("platformOtherProperty", "Nilai Properti Lain", "platform/otherProperty"),
        G("Rencana Akuisisi"),
        F("acquisitionPlanType", "Tipe Geometri Rencana", "acquisitionPlan/type"),
        F("acquisitionPlanStatus", "Status Rencana", "acquisitionPlan/status", "statusOptions"),
        F("acquisitionPlanTitle", "Judul Rencana", "acquisitionPlan/citation/title"),
        F("acquisitionPlanDate", "Tanggal Rencana", "acquisitionPlan/citation/date/date"),
    ]


ID = "identificationInfo/"
REPORT_SNIPS = [(o["label"], "report_" + o["value"]) for o in OPTS["qualityTypeOptions"]]
RESULT_SNIPS = [("Conformance Result", "res_conformance"), ("Quantitative Result", "res_quantitative"),
                ("Descriptive Result", "res_descriptive"), ("Coverage Result", "res_coverage")]
SECTIONS = [
    (1, "Informasi Metadata", "Identifier, Lokal, Scope, Tanggal, Standar", [
        G("Identifier & Lokal"),
        F("metadataIdentifier", "Metadata Identifier", "metadataIdentifier/code"),
        F("language", "Bahasa", "defaultLocale/language", "languageOptions"),
        F("country", "Negara", "defaultLocale/country", "countryOptions"),
        F("characterEncoding", "Character Encoding", "defaultLocale/characterEncoding", "encodingOptions"),
        F("parentMetadata", "Parent Metadata", "parentMetadata/title"),
        F("metadataScope", "Resource Scope", "metadataScope/resourceScope", "scopeOptions"),
        F("scopeName", "Scope Name", "metadataScope/name"),
        G("Tanggal Metadata"),
        L("Tanggal", "dateInfo", [F("date", "Tanggal Metadata", "date"),
                                  F("type", "Tipe Tanggal", "dateType", "dateTypeOptions")]),
        G("Standar Metadata"),
        F("metadataStandardTitle", "Judul Standar", "metadataStandard/title"),
        F("metadataStandardEdition", "Edisi Standar", "metadataStandard/edition"),
        G("Kontak Metadata"),
        L("Kontak", "contact", CONTACT()),
    ]),
    (2, "Identitas Data", "Identitas, Kontak, Cakupan, Keyword, Format", [
        T("Identitas"),
        F("dataTitle", "Judul Data", ID + "citation/title"),
        F("dataAlternateTitle", "Judul Alternatif", ID + "citation/alternateTitle"),
        F("dataAbstract", "Abstrak", ID + "abstract"),
        F("dataPurpose", "Tujuan", ID + "purpose"),
        F("dataCredit", "Kredit", ID + "credit"),
        F("dataStatus", "Status", ID + "status", "statusOptions"),
        F("dataCreationDate", "Tanggal Pembuatan", ID + "citation/date[=creation]/date"),
        F("dataPublicationDate", "Tanggal Publikasi", ID + "citation/date[=publication]/date"),
        F("dataRevisionDate", "Tanggal Revisi", ID + "citation/date[=revision]/date"),
        F("dataEdition", "Edisi", ID + "citation/edition"),
        F("dataEditionDate", "Tanggal Edisi Data", ID + "citation/editionDate"),
        F("presentationForm", "Bentuk Penyajian", ID + "citation/presentationForm"),
        F("dataOnlineResourceURL", "Online Resource URL", ID + "citation/onlineResource/linkage"),
        F("dataOnlineResourceName", "Online Resource Name", ID + "citation/onlineResource/name"),
        F("dataOnlineResourceProtocol", "Online Resource Protocol", ID + "citation/onlineResource/protocol"),
        F("dataOnlineResourceFunction", "Online Resource Function", ID + "citation/onlineResource/function", "onlineFunctionOptions"),
        G("Pihak Bertanggung Jawab atas Sitasi"),
        L("Kontak", ID + "citation/citedResponsibleParty", CONTACT()),
        T("Kontak"),
        L("Kontak", ID + "pointOfContact", CONTACT()),
        T("Cakupan & Topik"),
        G("Cakupan Wilayah"),
        F("extentDescription", "Deskripsi Cakupan Wilayah Data", ID + "extent/description"),
        F("westBound", "Batas Bujur Barat", ID + "extent/geographicElement[~EX_GeographicBoundingBox]/westBoundLongitude"),
        F("eastBound", "Batas Bujur Timur", ID + "extent/geographicElement[~EX_GeographicBoundingBox]/eastBoundLongitude"),
        F("southBound", "Batas Lintang Selatan", ID + "extent/geographicElement[~EX_GeographicBoundingBox]/southBoundLatitude"),
        F("northBound", "Batas Lintang Utara", ID + "extent/geographicElement[~EX_GeographicBoundingBox]/northBoundLatitude"),
        F("timeBegin", "Periode Awal", ID + "extent/temporalElement/extent/beginPosition"),
        F("timeEnd", "Periode Akhir", ID + "extent/temporalElement/extent/endPosition"),
        G("Topic Category"),
        L("Topic Category", ID + "topicCategory", [F("topicCategory", "Topic Category", ".", "topicCategoryOptions")]),
        T("Kata Kunci"),
        L("Kelompok Kata Kunci", ID + "descriptiveKeywords", [
            F("type", "Tipe", "type", "keywordTypeOptions"),
            L("Kata Kunci", "keyword", [F("value", "Kata Kunci", ".")])]),
        T("Format"),
        L("Format", ID + "resourceFormat", [
            F("formatTitle", "Format", "formatSpecificationCitation/title"),
            F("formatAlternateTitle", "Format (Nama Lengkap)", "formatSpecificationCitation/alternateTitle"),
            F("formatEdition", "Versi Format", "formatSpecificationCitation/edition")]),
        T("Penggunaan"),
        L("Penggunaan", ID + "resourceSpecificUsage", [
            F("specificUsage", "Penggunaan Spesifik", "specificUsage"),
            F("userRole", "Peran / Role", "userContactInfo/role", "roleOptions"),
            F("userOrganization", "Organisasi Pengguna", "userContactInfo/party/name"),
            F("userIndividual", "Posisi/jabatan pengguna", "userContactInfo/party/individual/positionName")]),
    ]),
    (3, "Representasi Spasial", "Tipe dan resolusi representasi spasial", [
        G("Tipe & Resolusi Spasial"),
        F("spatialRepresentationType", "Tipe Representasi Spasial", ID + "spatialRepresentationType", "spatialRepTypeOptions"),
        F("spatialResolution", "Resolusi Spasial (Denominator)", ID + "spatialResolution[1]/equivalentScale/denominator"),
        F("spatialResolutionM", "Resolusi Spasial (Meter)", ID + "spatialResolution[2]/distance"),
        G("Representasi Vektor"),
        O("Aktifkan Informasi Representasi Vektor", "spatialRepresentationInfo[~MD_VectorSpatialRepresentation]", "vector", [
            F("topologyLevel", "Tingkat Topologi (Topology Level)", "topologyLevel", "topologyOptions"),
            F("geometricObjectType", "Tipe Objek Geometri", "geometricObjects/geometricObjectType", "geometricObjectOptions"),
            F("geometricObjectCount", "Jumlah Objek Geometri", "geometricObjects/geometricObjectCount")]),
        G("Representasi Grid / Raster"),
        O("Aktifkan Informasi Grid / Raster Terektifikasi", "spatialRepresentationInfo[~MD_Georectified]", "grid", GRID()),
        O("Aktifkan Informasi Grid / Raster Georeferenceable (+ GCP)", "spatialRepresentationInfo[~MI_Georeferenceable]", "georef", GEOREF()),
    ]),
    (4, "Sistem Referensi Koordinat", "Sistem referensi koordinat / CRS", [
        G("Identitas Sistem Referensi Koordinat"),
        F("referenceSystemTitle", "Nama Sistem Referensi", "referenceSystemInfo/referenceSystemIdentifier/authority/title"),
        F("referenceSystemAlternateTitle", "Nama Alternatif", "referenceSystemInfo/referenceSystemIdentifier/authority/alternateTitle"),
        F("referenceSystemCode", "Kode", "referenceSystemInfo/referenceSystemIdentifier/code"),
        F("referenceSystemCodeSpace", "Code Space", "referenceSystemInfo/referenceSystemIdentifier/codeSpace"),
        F("referenceSystemType", "Tipe Sistem Referensi", "referenceSystemInfo/referenceSystemType", "referenceSystemTypeOptions"),
    ]),
    (5, "Informasi Konten", "Katalog unsur, cakupan, dan citra", [
        G("Katalog Unsur (Feature Catalogue)"),
        O("Aktifkan Informasi Katalog Unsur", "contentInfo[~MD_FeatureCatalogueDescription]", "featurecat", [
            F("featureCatalogueCompliance", "Kesesuaian dengan Katalog Unsur", "complianceCode"),
            F("featureCatalogueIncluded", "Termasuk dalam Dataset", "includedWithDataset"),
            L("Tipe Unsur (Feature Type)", "featureTypes", [F("name", "Nama Unsur (Feature)", "featureTypeName"),
                                                            F("code", "Kode / Code Space", "featureTypeName/@codeSpace")]),
            F("catalogueTitle", "Judul Katalog Unsur", "featureCatalogueCitation/title"),
            F("catalogueAlternateTitle", "Judul Alternatif Katalog", "featureCatalogueCitation/alternateTitle"),
            F("catalogueEdition", "Edisi Katalog", "featureCatalogueCitation/edition"),
            F("catalogueURL", "URL Katalog", "featureCatalogueCitation/onlineResource/linkage")]),
        G("Deskripsi Cakupan & Citra"),
        O("Aktifkan Deskripsi Cakupan (Coverage Description)", "contentInfo[~MD_CoverageDescription]", "coverage", COVERAGE()),
        O("Aktifkan Deskripsi Citra (Image Description)", "contentInfo[~MD_ImageDescription]", "image", IMAGE()),
    ]),
    (6, "Distribusi & Akses Data", "Informasi distribusi dan akses data", [
        G("Format Distribusi"),
        L("Format", "distributionInfo/distributionFormat", [
            F("title", "Nama Format", "formatSpecificationCitation/title"),
            F("alternateTitle", "Nama Lengkap Format", "formatSpecificationCitation/alternateTitle"),
            F("edition", "Versi", "formatSpecificationCitation/edition")]),
        G("Kontak Distributor"),
        L("Kontak", "distributionInfo/distributor/distributorContact", CONTACT()),
        G("Opsi Transfer"),
        F("distributionUnits", "Unit Distribusi", "distributionInfo/transferOptions/unitsOfDistribution"),
        F("transferSize", "Transfer Size (MB)", "distributionInfo/transferOptions/transferSize"),
        L("Akses Daring", "distributionInfo/transferOptions/onLine", ONLINE()),
    ]),
    (7, "Kualitas Data", "Laporan kualitas data", [
        G("Cakupan & Laporan Kualitas Data"),
        F("qualityScope", "Scope Kualitas Data", "dataQualityInfo/scope/level", "scopeOptions"),
        L("Laporan", "dataQualityInfo/report", [
            F("measure", "Nama Ukuran", "measure/nameOfMeasure"),
            F("description", "Deskripsi Ukuran", "measure/measureDescription"),
            F("evaluationMethodDescription", "Deskripsi Metode Evaluasi", "evaluationMethod/evaluationMethodDescription"),
            F("evaluationMethodType", "Tipe Metode Evaluasi", "evaluationMethod/evaluationMethodType", "evaluationMethodTypeOptions"),
            L("Hasil", "result", RESULT(), True, RESULT_SNIPS)], True, REPORT_SNIPS),
    ]),
    (8, "Riwayat Data", "Riwayat dan proses produksi data", [
        G("Pernyataan & Cakupan Lineage"),
        F("lineageStatement", "Deskripsi Lineage", "resourceLineage/statement"),
        F("lineageScopeLevel", "Scope Level Lineage", "resourceLineage/scope/level", "scopeOptions"),
        G("Sumber Data"),
        L("Sumber Data", "resourceLineage/source", SOURCE()),
        G("Tahap Proses"),
        L("Tahap Proses", "resourceLineage/processStep", STEP()),
    ]),
    (9, "Katalog Penyajian", "Referensi katalog penyajian", [
        G("Sitasi Katalog Penyajian"),
        F("portrayalCatalogueTitle", "Judul", "portrayalCatalogueInfo/portrayalCatalogueCitation/title"),
        F("portrayalCatalogueAlternateTitle", "Judul Alternatif", "portrayalCatalogueInfo/portrayalCatalogueCitation/alternateTitle"),
        F("portrayalCatalogueURL", "URL", "portrayalCatalogueInfo/portrayalCatalogueCitation/onlineResource/linkage"),
        G("Kontak"),
        L("Kontak", "portrayalCatalogueInfo/portrayalCatalogueCitation/citedResponsibleParty", CONTACT()),
    ]),
    (10, "Batasan & Keamanan", "Batasan akses, penggunaan, dan keamanan", [
        G("Batasan Data"),
        F("useLimitation", "Batasan Penggunaan", ID + "resourceConstraints[~MD_Constraints]/useLimitation"),
        F("accessConstraints", "Batasan Akses", ID + "resourceConstraints[~MD_LegalConstraints]/accessConstraints", "constraintOptions"),
        F("useConstraints", "Batasan Penggunaan (Legal)", ID + "resourceConstraints[~MD_LegalConstraints]/useConstraints", "constraintOptions"),
        F("otherConstraints", "Batasan Hukum Lainnya", ID + "resourceConstraints[~MD_LegalConstraints]/otherConstraints"),
        F("securityClassification", "Klasifikasi Keamanan", ID + "resourceConstraints[~MD_SecurityConstraints]/classification", "classificationOptions"),
        F("securityUserNote", "User Note Keamanan", ID + "resourceConstraints[~MD_SecurityConstraints]/userNote"),
        F("securitySystem", "Sistem Klasifikasi", ID + "resourceConstraints[~MD_SecurityConstraints]/classificationSystem"),
        F("handlingDescription", "Handling Description", ID + "resourceConstraints[~MD_SecurityConstraints]/handlingDescription"),
        G("Batasan Metadata"),
        F("metadataUseLimitation", "Batasan Penggunaan Metadata", "metadataConstraints[~MD_Constraints]/useLimitation"),
        F("metadataSecurityClassification", "Klasifikasi Keamanan Metadata", "metadataConstraints[~MD_SecurityConstraints]/classification", "classificationOptions"),
        F("metadataSecurityUserNote", "User Note Keamanan Metadata", "metadataConstraints[~MD_SecurityConstraints]/userNote"),
        F("metadataSecuritySystem", "Sistem Klasifikasi Metadata", "metadataConstraints[~MD_SecurityConstraints]/classificationSystem"),
        F("metadataOtherConstraints", "Batasan Hukum Lainnya Metadata", "metadataConstraints[~MD_LegalConstraints]/otherConstraints"),
    ]),
    (11, "Skema Aplikasi", "Informasi skema aplikasi / UML", [
        G("Informasi Skema Aplikasi"),
        F("schemaName", "Nama Schema", "applicationSchemaInfo/name/title"),
        F("schemaAlternateTitle", "Judul Alternatif", "applicationSchemaInfo/name/alternateTitle"),
        F("schemaLanguage", "Bahasa Schema", "applicationSchemaInfo/schemaLanguage"),
        F("schemaConstraintLanguage", "Bahasa Constraint", "applicationSchemaInfo/constraintLanguage"),
        F("schemaAscii", "Schema ASCII", "applicationSchemaInfo/schemaAscii"),
        F("schemaGraphicsURL", "Graphics URL", "applicationSchemaInfo/graphicsFile/linkage"),
        F("schemaGraphicsName", "Graphics Name", "applicationSchemaInfo/graphicsFile/name"),
    ]),
    (12, "Pemeliharaan", "Frekuensi dan tanggal pemeliharaan data serta metadata", [
        G("Pemeliharaan Data"),
        L("Pemeliharaan Data", ID + "resourceMaintenance", [
            F("maintenanceFrequency", "Frekuensi Pemeliharaan Data", "maintenanceAndUpdateFrequency", "maintenanceOptions"),
            F("maintenanceDate", "Tanggal Pemeliharaan / Update Data", "maintenanceDate/date"),
            F("maintenanceScopeLevel", "Cakupan Pemeliharaan Data", "maintenanceScope/level", "scopeOptions"),
            F("maintenanceNote", "Catatan Pemeliharaan Data", "maintenanceNote"),
            L("Kontak", "contact", CONTACT()),
        ]),
        G("Pemeliharaan Metadata"),
        F("metadataMaintenanceFrequency", "Frekuensi Pemeliharaan Metadata", "metadataMaintenance/maintenanceAndUpdateFrequency", "maintenanceOptions"),
        F("metadataMaintenanceDate", "Tanggal Pemeliharaan / Update Metadata", "metadataMaintenance/maintenanceDate/date"),
        F("metadataMaintenanceScopeLevel", "Cakupan Pemeliharaan Metadata", "metadataMaintenance/maintenanceScope/level", "scopeOptions"),
        F("metadataMaintenanceNote", "Catatan Pemeliharaan Metadata", "metadataMaintenance/maintenanceNote"),
        L("Kontak", "metadataMaintenance/contact", CONTACT()),
    ]),
    (13, "Ekstensi Metadata", "Ekstensi metadata dan informasi akuisisi (opsional)", [
        G("Sumber Daring Ekstensi"),
        F("extensionOnlineURL", "Linkage URL", "metadataExtensionInfo/extensionOnLineResource/linkage"),
        F("extensionOnlineProtocol", "Protocol", "metadataExtensionInfo/extensionOnLineResource/protocol"),
        F("extensionOnlineApplicationProfile", "Application Profile", "metadataExtensionInfo/extensionOnLineResource/applicationProfile"),
        F("extensionOnlineName", "Nama", "metadataExtensionInfo/extensionOnLineResource/name"),
        F("extensionOnlineDescription", "Deskripsi", "metadataExtensionInfo/extensionOnLineResource/description"),
        F("extensionOnlineFunction", "Fungsi Sumber Daring", "metadataExtensionInfo/extensionOnLineResource/function", "onlineFunctionOptions"),
        G("Elemen Ekstensi"),
        F("extendedElementName", "Nama Elemen", "metadataExtensionInfo/extendedElementInformation/name"),
        F("extendedElementDefinition", "Definisi", "metadataExtensionInfo/extendedElementInformation/definition"),
        F("extendedElementObligation", "Kewajiban Elemen", "metadataExtensionInfo/extendedElementInformation/obligation"),
        F("extendedElementCondition", "Kondisi", "metadataExtensionInfo/extendedElementInformation/condition"),
        F("extendedElementDataType", "Tipe Data", "metadataExtensionInfo/extendedElementInformation/dataType"),
        F("extendedElementMaxOccurrence", "Kemunculan Maksimum", "metadataExtensionInfo/extendedElementInformation/maximumOccurrence"),
        F("extendedElementDomainValue", "Nilai Domain", "metadataExtensionInfo/extendedElementInformation/domainValue"),
        F("extendedElementParentEntity", "Entitas Induk", "metadataExtensionInfo/extendedElementInformation/parentEntity"),
        F("extendedElementRule", "Aturan", "metadataExtensionInfo/extendedElementInformation/rule"),
        F("extendedElementRationale", "Alasan", "metadataExtensionInfo/extendedElementInformation/rationale"),
        G("Informasi Akuisisi"),
        O("Aktifkan Informasi Akuisisi", "acquisitionInformation", "acquisition", ACQUISITION()),
    ]),
]


# ------------------------------------------------------------------ pengikat path -> elemen
_SEG = re.compile(r"^(\w+|\.)(?:\[(.+)\])?$")


def _direct(E, name):
    c = [k for k in E if local(k.tag) == name or local(k.tag).lower() == name.lower()]
    if c:
        return E, c
    for cls in E:
        if local(cls.tag)[:1].isupper():
            c = [k for k in cls if local(k.tag) == name or local(k.tag).lower() == name.lower()]
            if c:
                return cls, c
    return E, []


def _ok(k, sel):
    if sel is None or sel.isdigit():
        return True
    if sel.startswith("="):
        return any(e.attrib.get("codeListValue") == sel[1:] for e in k.iter())
    if sel.startswith("~"):
        return any(local(g.tag) == sel[1:] for g in k)
    return True


def resolve(E, path):
    for seg in path.split("/"):
        if E is None:
            return None
        if seg in (".", ""):
            continue
        m = _SEG.match(seg)
        if not m:
            return None
        _, kids = _direct(E, m.group(1))
        kids = [k for k in kids if _ok(k, m.group(2))]
        if m.group(2) and m.group(2).isdigit():
            i = int(m.group(2)) - 1
            kids = kids[i:i + 1]
        E = kids[0] if kids else None
    return E


def group(base, path):
    """(container, [instans]) untuk path daftar berulang."""
    segs = path.split("/")
    parent = resolve(base, "/".join(segs[:-1])) if len(segs) > 1 else base
    if parent is None:
        return None, []
    return _direct(parent, segs[-1])


def class_of(el):
    """Elemen kelas yang memuat properti anak dari `el` (el sendiri bila sudah kelas / akar)."""
    if local(el.tag)[:1].isupper():
        return el
    for c in el:
        if local(c.tag)[:1].isupper():
            return c
    return el


def leaf_field(prop):
    if prop is None:
        return None
    if model.is_value(prop):
        return Field([], prop, "value")
    n = local(prop.tag)
    if "codeListValue" in prop.attrib:
        return Field([], prop, "code")
    if n in ENUM_TEXT:
        return Field([], prop, "enum")
    for k in prop:
        n = local(k.tag)
        if model.is_value(k):
            return Field([], k, "value")
        if "codeListValue" in k.attrib:
            return Field([], k, "code")
        if n in ENUM_TEXT:
            return Field([], k, "enum")
        for sub in k:
            if model.is_value(sub):
                return Field([], sub, "value")
            if "codeListValue" in sub.attrib:
                return Field([], sub, "code")
    return Field([], prop, "wrapper") if len(prop) == 0 else None


def names_of(path):
    path = re.sub(r"#\d$", "", path)
    segs = [re.sub(r"\[.*\]", "", x) for x in path.split("/")]
    segs = [x for x in segs if x and x != "." and not x.startswith("@")]
    if not segs:
        return "", ()
    return segs[0], tuple(x for x in segs[1:] if not x[:1].isupper())


def make_field(base, sp):
    path, extra, kind = sp.path, None, None
    m = re.search(r"#(\d)$", path)
    if m:
        extra, kind, path = int(m.group(1)), "pos", path[:m.start()]
    elif "@" in path:
        path, attr = path.rsplit("@", 1)
        extra, kind, path = attr, "attr", path.rstrip("/")
    el = resolve(base, path or ".")
    if el is None and path.endswith("/date"):
        el = resolve(base, path[:-5])
    if el is None:
        return None
    if kind == "pos":
        return Field([], el, "pos", extra) if local(el.tag) == "pos" else None
    f = leaf_field(el)
    if f is not None and kind == "attr":
        return Field([], f.el, "attr", extra)
    return f


# ------------------------------------------------------------------ penanganan elemen hilang dari template
_TEMPLATE_ROOT = None


def get_template_root():
    global _TEMPLATE_ROOT
    if _TEMPLATE_ROOT is None:
        try:
            tmpl_path = os.path.join(os.path.dirname(__file__), "template.xml")
            if os.path.exists(tmpl_path):
                _TEMPLATE_ROOT = model.load(tmpl_path)[0]
        except Exception:
            _TEMPLATE_ROOT = None
    return _TEMPLATE_ROOT


def clear_element_values(el, preserve_code=None):
    if local(el.tag) == "CI_DateTypeCode" and el.attrib.get("codeListValue") == "lastUpdate":
        return
    el.text = ""
    if "codeListValue" in el.attrib:
        if preserve_code is None or not preserve_code:
            el.attrib["codeListValue"] = ""
    for c in el:
        clear_element_values(c)


def insert_child_in_order(parent, new_child, tmpl_parent):
    if tmpl_parent is None:
        parent.append(new_child)
        return
    tmpl_tags = [local(c.tag) for c in tmpl_parent]
    child_tag = local(new_child.tag)
    target_idx = tmpl_tags.index(child_tag) if child_tag in tmpl_tags else len(tmpl_tags)
    insert_at = len(parent)
    for i, existing in enumerate(parent):
        ext_tag = local(existing.tag)
        if ext_tag in tmpl_tags and tmpl_tags.index(ext_tag) > target_idx:
            insert_at = i
            break
    parent.insert(insert_at, new_child)


def ensure_path(base, path, tmpl_root):
    if base is None or tmpl_root is None:
        return None
    existing = resolve(base, path)
    if existing is not None:
        return existing

    segs = [s for s in path.split("/") if s and s != "."]
    curr_base = base
    curr_tmpl = tmpl_root

    for seg in segs:
        m = _SEG.match(seg)
        tag_name = m.group(1) if m else seg

        next_base = resolve(curr_base, seg)
        next_tmpl = resolve(curr_tmpl, seg)

        if next_base is None:
            if next_tmpl is None:
                return None
            matching_child = None
            for c in curr_tmpl:
                if local(c.tag) == tag_name:
                    matching_child = c
                    break
            if matching_child is None:
                for cls in curr_tmpl:
                    if local(cls.tag)[:1].isupper():
                        for c in cls:
                            if local(c.tag) == tag_name:
                                matching_child = c
                                break
                        if matching_child is not None:
                            break
            if matching_child is None:
                matching_child = next_tmpl

            new_child = copy.deepcopy(matching_child)
            preserve_code = m.group(2)[1:] if (m and m.group(2) and m.group(2).startswith("=")) else None
            clear_element_values(new_child, preserve_code=preserve_code)

            target_container = curr_base
            for cls in curr_base:
                if local(cls.tag)[:1].isupper():
                    target_container = cls
                    break

            tmpl_container = curr_tmpl
            for cls in curr_tmpl:
                if local(cls.tag)[:1].isupper():
                    tmpl_container = cls
                    break

            insert_child_in_order(target_container, new_child, tmpl_container)
            next_base = resolve(curr_base, seg)

        curr_base = next_base
        curr_tmpl = next_tmpl
        if curr_base is None:
            break

    return curr_base


class VirtualField:
    """Field aktif untuk elemen yang belum ada pada berkas XML yang diunggah/dimuat.
    Nilai awal kosong/null. Form isian tetap aktif. Bila diisi oleh pengguna, struktur elemen
    dari template.xml dibuat pada pohon XML sehingga dapat disimpan dan diekspor."""
    def __init__(self, base, sp, root, prefix=""):
        self.base = base
        self.sp = sp
        self.root = root
        self.prefix = prefix.strip("/") if prefix else ""
        self.full_path = (self.prefix + "/" + sp.path) if self.prefix else sp.path
        self.trail = [sp.key]
        self.section = ""
        self.val = ""
        self.extra = None
        self.kind = "value"

        tmpl_root = get_template_root()
        tmpl_f = None
        if tmpl_root is not None:
            tmpl_base = resolve(tmpl_root, self.prefix) if self.prefix else tmpl_root
            if tmpl_base is not None:
                tmpl_f = make_field(tmpl_base, sp)
            if tmpl_f is None and self.full_path != sp.path:
                dummy_sp = F(sp.key, sp.label, self.full_path, sp.opts)
                tmpl_f = make_field(tmpl_root, dummy_sp)

        self.tmpl_f = tmpl_f
        if tmpl_f is not None:
            self.value_name = tmpl_f.value_name
            self.kind = tmpl_f.kind
            self.extra = tmpl_f.extra
        else:
            k = (sp.key + " " + sp.path).lower()
            if any(x in k for x in ("date", "time", "position")) and not ("type" in k):
                self.value_name = "DateTime" if ("datetime" in k or "stepdatetime" in k) else "Date"
            elif sp.opts or "code" in k:
                self.value_name = "CharacterString"
                self.kind = "code" if sp.opts else "value"
            else:
                self.value_name = "CharacterString"

    @property
    def names(self):
        return tuple(re.sub(r"\[\d+\].*", "", t) for t in self.trail)

    @property
    def label(self):
        return " › ".join(self.trail) if self.trail else self.value_name

    @property
    def multiline(self):
        return self.sp.key in MULTILINE or (self.tmpl_f.multiline if self.tmpl_f else False)

    @property
    def options(self):
        if self.tmpl_f and self.tmpl_f.options:
            return self.tmpl_f.options
        if self.kind in ("code", "enum"):
            return model.CODELISTS.get(self.value_name, [])
        return []

    def get(self):
        real_f = make_field(self.base, self.sp)
        if real_f is not None:
            return real_f.get()
        return self.val

    def set(self, text):
        self.val = text if self.multiline else text.strip()
        if not self.val:
            return
        tmpl_root = get_template_root()
        if tmpl_root is not None:
            if self.base is self.root or not self.prefix:
                ensure_path(self.root, self.full_path, tmpl_root)
            else:
                tmpl_base = resolve(tmpl_root, self.prefix)
                res = ensure_path(self.base, self.sp.path, tmpl_base if tmpl_base is not None else tmpl_root)
                if res is None:
                    ensure_path(self.root, self.full_path, tmpl_root)
        real_f = make_field(self.base, self.sp)
        if real_f is not None:
            real_f.set(self.val)


# ------------------------------------------------------------------ simpul hasil
class BField:
    def __init__(self, spec, field, options):
        self.spec = spec
        self.key, self.label, self.field, self.options = spec.key, spec.label, field, options
        self.desc = DESC.get(spec.key, "")


class BGroup:
    def __init__(self, label): self.label = label


class BTab:
    def __init__(self, label): self.label = label


class BNote:
    def __init__(self, text): self.text = text


class BInst:
    def __init__(self, el, title, nodes, removable):
        self.el, self.title, self.nodes, self.removable = el, title, nodes, removable


class BList:
    """options = [(label, sumber)] ; sumber = elemen (klon) atau ('snip', nama)."""
    def __init__(self, title, container, instances, options, can_add=True):
        self.title, self.container, self.instances = title, container, instances
        self.options, self.can_add = options, can_add


class BOptional:
    def __init__(self, label, present, container, snippet, nodes, el):
        self.label, self.present, self.container = label, present, container
        self.snippet, self.nodes, self.el = snippet, nodes, el


class BSection:
    def __init__(self, sid, label, caption, nodes):
        self.id, self.label, self.caption, self.nodes = sid, label, caption, nodes


def _options(spec, f):
    if spec.opts:
        return [(o["label"], o["value"], o.get("description", "")) for o in OPTS[spec.opts]]
    if f is not None and f.kind in ("code", "enum"):
        return [(v, v, "") for v in model.CODELISTS.get(f.value_name, [])]
    return None


def _nodes(base, specs, root, top, missing, prefix=""):
    out = []
    for sp in specs:
        if isinstance(sp, G):
            out.append(BGroup(sp.label))
        elif isinstance(sp, T):
            out.append(BTab(sp.label))
        elif isinstance(sp, N):
            out.append(BNote(sp.text))
        elif isinstance(sp, F):
            f = make_field(base, sp)
            if f is None:
                if not sp.hide:
                    f = VirtualField(base, sp, root, prefix)
                    full = (prefix + "/" + sp.path) if prefix else sp.path
                    sec, names = names_of(full)
                    f.trail = list(names) or [sp.key]
                    if top:
                        f.section = sec
                    out.append(BField(sp, f, _options(sp, f)))
                continue
            full = (prefix + "/" + sp.path) if prefix else sp.path
            sec, names = names_of(full)
            f.trail = list(names) or [sp.key]
            if top:
                f.section = sec
            out.append(BField(sp, f, _options(sp, f)))
        elif isinstance(sp, O):
            el = resolve(base, sp.path)
            container = class_of(base)
            nodes = []
            if el is not None:
                full = (prefix + "/" + sp.path) if prefix else sp.path
                nodes = _nodes(el, sp.items, root, top, missing, full if top else "")
            out.append(BOptional(sp.label, el is not None, container, sp.snippet, nodes, el))
        elif isinstance(sp, L):
            container, kids = group(base, sp.path)
            if not kids:
                tmpl_root = get_template_root()
                if tmpl_root is not None:
                    tmpl_base = resolve(tmpl_root, prefix) if prefix else tmpl_root
                    ensure_path(base, sp.path, tmpl_base if tmpl_base is not None else tmpl_root)
                    container, kids = group(base, sp.path)
            if not kids:
                missing.append(prefix + sp.path)
                continue
            prop = sp.path.split("/")[-1]
            if sp.snips:
                opts = [(lab, ("snip", name)) for lab, name in sp.snips]
            else:
                opts = model._options(kids)
            insts = []
            full_l = (prefix.rstrip("/") + "/" + sp.path.lstrip("/")) if prefix else sp.path.rstrip("/")
            for i, k in enumerate(kids, 1):
                title = "%s %d" % (sp.title, i)
                if sp.show_class and len(k):
                    title += " (%s)" % local(k[0].tag)
                insts.append(BInst(k, title, _nodes(k, sp.items, root, False, missing, full_l), len(kids) > 1))
            bl = BList(sp.title, container, insts, opts, model.can_add(container, prop, len(kids)))
            bl.path = sp.path
            out.append(bl)
    return out


def build(root):
    """Kembalikan (daftar BSection, daftar path yang tidak ditemukan)."""
    missing = []
    secs = [BSection(sid, label, cap, _nodes(root, specs, root, True, missing))
            for sid, label, cap, specs in SECTIONS]
    return secs, missing


def iter_fields(nodes):
    for n in nodes:
        if isinstance(n, BField) and n.field is not None:
            yield n
        elif isinstance(n, BOptional):
            yield from iter_fields(n.nodes)
        elif isinstance(n, BList):
            for inst in n.instances:
                yield from iter_fields(inst.nodes)
