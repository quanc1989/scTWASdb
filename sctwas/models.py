# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


# Create your models here.
class Task(models.Model):
    field_id = models.CharField(db_column='_id', primary_key=True, max_length=100)  # Field renamed because it started with '_'.
    progress = models.IntegerField()
    name = models.CharField(max_length=100, blank=True, null=True)
    mail = models.CharField(max_length=100, blank=True, null=True)
    create_timestamp = models.DateTimeField(blank=True, null=True)
    last_edit_timestamp = models.DateTimeField(blank=True, null=True)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'task'


class Celltype(models.Model):
    majortype = models.CharField(max_length=100)
    subtype = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)
    celltypeid = models.CharField(db_column='celltypeID', max_length=100, primary_key=True)  # Field name made lowercase.
    collectionid = models.CharField(db_column='collectionID', max_length=100)  # Field name made lowercase.
    studyid = models.CharField(db_column='studyID', max_length=100)  # Field name made lowercase.

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'celltype'


class SNP(models.Model):
    chrom = models.CharField(max_length=100)
    pos = models.IntegerField()
    rsid = models.CharField(db_column='rsID', max_length=100, primary_key=True)  # Field name made lowercase.
    ref = models.TextField()
    alt = models.TextField()

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'dbsnp'


class Eqtl(models.Model):
    rsid = models.CharField(db_column='rsID', max_length=100, primary_key=True)  # Field name made lowercase.
    beta = models.FloatField()
    se = models.FloatField()
    pvalue = models.FloatField()
    genename = models.CharField(max_length=100)
    celltype = models.CharField(max_length=100)
    collectionid = models.CharField(db_column='collectionID', max_length=100)  # Field name made lowercase.

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'eqtl'


class Gene(models.Model):
    chrom = models.CharField(max_length=100)
    genestart = models.IntegerField(db_column='geneStart')  # Field name made lowercase.
    geneend = models.IntegerField(db_column='geneEnd')  # Field name made lowercase.
    ensemblid = models.CharField(db_column='ensemblID', max_length=100, primary_key=True)  # Field name made lowercase.
    genename = models.CharField(db_column='geneName', max_length=100)  # Field name made lowercase.

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'gene'


class Study(models.Model):
    studyid = models.CharField(db_column='studyID', max_length=100, primary_key=True)  # Field name made lowercase.
    title = models.TextField()
    method = models.CharField(max_length=100)
    sample = models.CharField(max_length=100)
    journal = models.CharField(max_length=100)
    year = models.CharField(max_length=100)
    doi = models.CharField(max_length=100)
    authors = models.TextField()
    samplesize = models.IntegerField(db_column='sampleSize')  # Field name made lowercase.
    modelsize = models.IntegerField(db_column='modelSize')  # Field name made lowercase.

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'study'

class Trait(models.Model):
    phecode = models.CharField(db_column='pheCode', primary_key=True, max_length=100)  # Field name made lowercase.
    description = models.TextField()
    icd10 = models.CharField(db_column='ICD10', max_length=100)  # Field name made lowercase.
    n = models.CharField(db_column='N', max_length=100)  # Field name made lowercase.
    n_case = models.CharField(db_column='N_case', max_length=100)  # Field name made lowercase.
    n_control = models.CharField(db_column='N_control', max_length=100)  # Field name made lowercase.
    ratio = models.CharField(max_length=100)
    url = models.TextField()

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'trait'


class Twas(models.Model):
    ensemblid = models.CharField(primary_key=True, db_column='ensemblID', max_length=100)  # Field name made lowercase.
    phecode = models.CharField(db_column='pheCode', max_length=100)  # Field name made lowercase.
    n_snps = models.IntegerField()
    fusion_z = models.FloatField(db_column='FUSION_Z')  # Field name made lowercase.
    fusion_pval = models.FloatField(db_column='FUSION_PVAL')  # Field name made lowercase.
    spred_z = models.FloatField(db_column='SPred_Z')  # Field name made lowercase.
    spred_pval = models.FloatField(db_column='SPred_PVAL')  # Field name made lowercase.
    celltype = models.CharField(max_length=100)
    collectionid = models.CharField(db_column='collectionID', max_length=100)  # Field name made lowercase.

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__[item]

    class Meta:
        managed = False
        db_table = 'twas'