"""Compatibility entry points for the original Explore API."""
from sctwas.explore import all_results, parameters


def search(key, celltype, category, threshold, value, eqtl_threshold=1):
    return all_results(parameters(dict(key=key, celltype=celltype, icd10=category,
        thres_twas=threshold, thres=eqtl_threshold, data=value)))


def getTraitsByDescription(celltypeID, icd10ID, twasThres, queryData):
    return search('1', celltypeID, icd10ID, twasThres, queryData)


def getTraitsByGeneName(celltypeID, icd10ID, twasThres, queryData):
    return search('0', celltypeID, icd10ID, twasThres, queryData)


def getTraitsByEnsembleID(celltypeID, icd10ID, twasThres, queryData):
    return search('4', celltypeID, icd10ID, twasThres, queryData)


def getTraitsBySNP(celltypeID, icd10ID, eQTLthres, twasThres, queryData):
    return search('2', celltypeID, icd10ID, twasThres, queryData, eQTLthres)


def getTraitsByCelltype(celltypeID, icd10ID, twasThres, queryData):
    return search('3', celltypeID, icd10ID, twasThres, queryData)
