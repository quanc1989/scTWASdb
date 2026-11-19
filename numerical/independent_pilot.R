# Independent scalar/matrix formulas. Does not call TIGAR or Python helpers.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==3)
mode <- args[[1]]; input <- args[[2]]; output <- args[[3]]
if (file.exists(output)) stop('Preserve existing independent result')
logtail <- function(z) if(is.finite(z)) log(2)+pnorm(-abs(z),log.p=TRUE) else NA_real_
ptail <- function(z) if(is.finite(z)) 2*pnorm(-abs(z)) else NA_real_
options(digits=17)
if(mode=='tails') {
  x <- read.csv(input,stringsAsFactors=FALSE)
  x$z <- suppressWarnings(as.numeric(x$z_text))
  x$p <- vapply(x$z,ptail,0.0)
  x$log_p <- vapply(x$z,logtail,0.0)
  write.table(x,output,sep=',',row.names=FALSE,quote=TRUE,na='NA')
} else if(mode=='inputs') {
  index <- read.csv(input,stringsAsFactors=FALSE)
  results <- list()
  for(i in seq_len(nrow(index))) {
    d <- read.csv(index$ledger[[i]],colClasses='character',check.names=FALSE)
    keep <- d$disposition=='retained'
    x <- d[keep,]
    sign <- ifelse(x$A1==x$ALT & x$A2==x$REF,1,
                   ifelse(x$A1==x$REF & x$A2==x$ALT,-1,NA_real_))
    z <- sign*as.numeric(x$BETA)/as.numeric(x$SE)
    delta <- abs(z-as.numeric(x$z_full))
    results[[i]] <- data.frame(trait=index$trait[[i]],rows=nrow(d),retained=nrow(x),
      palindromic_excluded=sum(d$disposition=='palindromic_without_frequency_resolution'),
      raw_coordinates_preserved=all(nzchar(d$raw_POS) & d$raw_CHR=='22'),
      effect_sign_correct=all(is.finite(sign) & sign==as.numeric(x$sign)),
      unique_derived_positions=anyDuplicated(x$POS)==0,
      max_beta_se_delta=max(delta),full_precision_consistent=all(delta<=1e-14*pmax(1,abs(z))),
      rounded_consistent=all(abs(round(z,4)-as.numeric(x$z_rounded))<=1e-14),
      rejected_no_derived_z=all(!nzchar(d$z_full[!keep])))
  }
  write.table(do.call(rbind,results),output,sep=',',row.names=FALSE,quote=TRUE,na='NA')
} else if(mode=='matrix') {
  index <- read.csv(input,stringsAsFactors=FALSE)
  results <- list()
  for(i in seq_len(nrow(index))) {
    item <- index[i,]
    d <- read.delim(item$vectors,stringsAsFactors=FALSE,check.names=FALSE)
    n <- nrow(d)
    con <- file(item$covariance,'rb')
    raw <- readBin(con,'double',n=n*n,size=8,endian='little'); close(con)
    if(length(raw)!=n*n) stop('Covariance size mismatch')
    V <- matrix(raw,nrow=n,byrow=TRUE)
    if(any(!is.finite(V)) || any(!is.finite(d$z))) stop('Unreviewed nonfinite LD or GWAS operand')
    # Diagnostic cases deliberately retain bad original weights. Do not impute
    # them or suppress their resulting NA/NaN statistics.
    if(any(!is.finite(d$w)) && item$role!='failure_mechanism_diagnostic')
      stop('Nonfinite weights outside the predeclared diagnostic scope')
    if(!isTRUE(all.equal(V,t(V),tolerance=0))) stop('Non-symmetric captured LD')
    sd <- suppressWarnings(sqrt(diag(V)))
    C <- V / outer(sd,sd)
    C[V==0] <- 0
    qf <- as.numeric(t(d$w) %*% C %*% d$w)
    qs <- as.numeric(t(d$w) %*% V %*% d$w)
    zf <- suppressWarnings(sum(d$w*d$z) / sqrt(qf))
    zs <- suppressWarnings(sum(d$w*d$z*sd) / sqrt(qs))
    eig <- eigen(V,symmetric=TRUE,only.values=TRUE)$values
    results[[i]] <- data.frame(run_name=item$run_name,gene=item$gene,n_snps=n,
      FUSION_Z=zf,FUSION_p=ptail(zf),FUSION_log_p=logtail(zf),
      SPred_Z=zs,SPred_p=ptail(zs),SPred_log_p=logtail(zs),
      fusion_quadratic=qf,spred_quadratic=qs,
      fusion_numerator=sum(d$w*d$z),spred_numerator=sum(d$w*d$z*sd),
      min_ld_eigenvalue=min(eig),zero_ld_diagonals=sum(diag(V)==0),
      negative_ld_diagonals=sum(diag(V)<0),
      nonfinite_weights=sum(!is.finite(d$w)),nonfinite_gwas_z=sum(!is.finite(d$z)),
      sd_consistent=isTRUE(all.equal(sd,d$sd,tolerance=1e-14)))
  }
  write.table(do.call(rbind,results),output,sep=',',row.names=FALSE,quote=TRUE,na='NA')
} else stop('Unknown mode')
