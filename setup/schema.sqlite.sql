-- Empty scTWAS application schema. Metadata keys may repeat in the imported catalogue.

CREATE TABLE "celltype" (
  "majortype" TEXT NOT NULL,
  "subtype" TEXT NOT NULL,
  "condition" TEXT NOT NULL,
  "celltypeID" TEXT NOT NULL,
  "collectionID" TEXT NOT NULL,
  "studyID" TEXT NOT NULL
);

CREATE INDEX "celltype_celltypeIDIndex" ON "celltype" ("celltypeID");

CREATE INDEX "celltype_collectionIDIndex" ON "celltype" ("collectionID");

CREATE TABLE "dbsnp" (
  "chrom" TEXT NOT NULL,
  "pos" INTEGER NOT NULL,
  "rsID" TEXT NOT NULL,
  "ref" TEXT NOT NULL,
  "alt" TEXT NOT NULL
);

CREATE INDEX "dbsnp_posIndex" ON "dbsnp" ("chrom", "pos");

CREATE INDEX "dbsnp_rsIDIndex" ON "dbsnp" ("rsID");

CREATE TABLE "eqtl" (
  "rsID" TEXT NOT NULL,
  "beta" REAL NOT NULL,
  "se" REAL NOT NULL,
  "pvalue" REAL NOT NULL,
  "genename" TEXT NOT NULL,
  "celltype" TEXT NOT NULL,
  "collectionID" TEXT NOT NULL
);

CREATE INDEX "eqtl_geneIndex" ON "eqtl" ("genename", "celltype", "collectionID");

CREATE INDEX "eqtl_rsIDIndex" ON "eqtl" ("rsID");

CREATE TABLE "gene" (
  "chrom" TEXT NOT NULL,
  "geneStart" INTEGER NOT NULL,
  "geneEnd" INTEGER NOT NULL,
  "ensemblID" TEXT NOT NULL,
  "geneName" TEXT NOT NULL
);

CREATE INDEX "gene_ensemblIDIndex" ON "gene" ("ensemblID");

CREATE INDEX "gene_geneNameIndex" ON "gene" ("geneName");

CREATE INDEX "gene_posIndex" ON "gene" ("chrom", "geneStart", "geneEnd");

CREATE TABLE "study" (
  "studyID" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "method" TEXT NOT NULL,
  "sample" TEXT NOT NULL,
  "journal" TEXT NOT NULL,
  "year" TEXT NOT NULL,
  "doi" TEXT NOT NULL,
  "authors" TEXT NOT NULL,
  "sampleSize" INTEGER NOT NULL,
  "modelSize" INTEGER NOT NULL
);

CREATE INDEX "study_studyIDIndex" ON "study" ("studyID");

CREATE TABLE "task" (
  "_id" TEXT NOT NULL,
  "progress" INTEGER NOT NULL,
  "name" TEXT,
  "mail" TEXT,
  "create_timestamp" TEXT,
  "last_edit_timestamp" TEXT,
  PRIMARY KEY ("_id")
);

CREATE TABLE "trait" (
  "pheCode" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "ICD10" TEXT NOT NULL,
  "N" TEXT NOT NULL,
  "N_case" TEXT NOT NULL,
  "N_control" TEXT NOT NULL,
  "ratio" TEXT NOT NULL,
  "url" TEXT NOT NULL,
  PRIMARY KEY ("pheCode")
);

CREATE INDEX "trait_ICD10Index" ON "trait" ("ICD10");

CREATE TABLE "twas" (
  "ensemblID" TEXT NOT NULL,
  "pheCode" TEXT NOT NULL,
  "n_snps" INTEGER NOT NULL,
  "FUSION_Z" REAL NOT NULL,
  "FUSION_PVAL" REAL NOT NULL,
  "SPred_Z" REAL NOT NULL,
  "SPred_PVAL" REAL NOT NULL,
  "celltype" TEXT NOT NULL,
  "collectionID" TEXT NOT NULL
);

CREATE INDEX "twas_geneIndex" ON "twas" ("ensemblID", "celltype", "collectionID");

CREATE INDEX "twas_pheIndex" ON "twas" ("pheCode", "celltype", "collectionID");
