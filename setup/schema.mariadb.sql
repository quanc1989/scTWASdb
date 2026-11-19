-- Empty scTWAS application schema. Metadata keys may repeat in the imported catalogue.

CREATE TABLE `celltype` (
  `majortype` varchar(100) NOT NULL,
  `subtype` varchar(100) NOT NULL,
  `condition` varchar(100) NOT NULL,
  `celltypeID` varchar(100) NOT NULL,
  `collectionID` varchar(100) NOT NULL,
  `studyID` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `celltype_celltypeIDIndex` ON `celltype` (`celltypeID`);

CREATE INDEX `celltype_collectionIDIndex` ON `celltype` (`collectionID`);

CREATE TABLE `dbsnp` (
  `chrom` varchar(100) NOT NULL,
  `pos` int(11) NOT NULL,
  `rsID` varchar(100) NOT NULL,
  `ref` text NOT NULL,
  `alt` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `dbsnp_posIndex` ON `dbsnp` (`chrom`, `pos`);

CREATE INDEX `dbsnp_rsIDIndex` ON `dbsnp` (`rsID`);

CREATE TABLE `eqtl` (
  `rsID` varchar(100) NOT NULL,
  `beta` double NOT NULL,
  `se` double NOT NULL,
  `pvalue` double NOT NULL,
  `genename` varchar(100) NOT NULL,
  `celltype` varchar(100) NOT NULL,
  `collectionID` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `eqtl_geneIndex` ON `eqtl` (`genename`, `celltype`, `collectionID`);

CREATE INDEX `eqtl_rsIDIndex` ON `eqtl` (`rsID`);

CREATE TABLE `gene` (
  `chrom` varchar(100) NOT NULL,
  `geneStart` int(11) NOT NULL,
  `geneEnd` int(11) NOT NULL,
  `ensemblID` varchar(100) NOT NULL,
  `geneName` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `gene_ensemblIDIndex` ON `gene` (`ensemblID`);

CREATE INDEX `gene_geneNameIndex` ON `gene` (`geneName`);

CREATE INDEX `gene_posIndex` ON `gene` (`chrom`, `geneStart`, `geneEnd`);

CREATE TABLE `study` (
  `studyID` varchar(100) NOT NULL,
  `title` text NOT NULL,
  `method` varchar(100) NOT NULL,
  `sample` varchar(100) NOT NULL,
  `journal` varchar(100) NOT NULL,
  `year` varchar(100) NOT NULL,
  `doi` varchar(100) NOT NULL,
  `authors` text NOT NULL,
  `sampleSize` int(11) NOT NULL,
  `modelSize` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `study_studyIDIndex` ON `study` (`studyID`);

CREATE TABLE `task` (
  `_id` varchar(100) NOT NULL,
  `progress` int(11) NOT NULL,
  `name` varchar(100),
  `mail` varchar(100),
  `create_timestamp` datetime,
  `last_edit_timestamp` datetime,
  PRIMARY KEY (`_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `trait` (
  `pheCode` varchar(100) NOT NULL,
  `description` text NOT NULL,
  `ICD10` varchar(100) NOT NULL,
  `N` varchar(100) NOT NULL,
  `N_case` varchar(100) NOT NULL,
  `N_control` varchar(100) NOT NULL,
  `ratio` varchar(100) NOT NULL,
  `url` text NOT NULL,
  PRIMARY KEY (`pheCode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `trait_ICD10Index` ON `trait` (`ICD10`);

CREATE TABLE `twas` (
  `ensemblID` varchar(100) NOT NULL,
  `pheCode` varchar(100) NOT NULL,
  `n_snps` int(11) NOT NULL,
  `FUSION_Z` double NOT NULL,
  `FUSION_PVAL` double NOT NULL,
  `SPred_Z` double NOT NULL,
  `SPred_PVAL` double NOT NULL,
  `celltype` varchar(100) NOT NULL,
  `collectionID` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX `twas_geneIndex` ON `twas` (`ensemblID`, `celltype`, `collectionID`);

CREATE INDEX `twas_pheIndex` ON `twas` (`pheCode`, `celltype`, `collectionID`);
