configfile: "config.yaml"

import os
import glob

def get_ids_from_path_pattern(path_pattern):
    ids = sorted([os.path.basename(os.path.splitext(val)[0])
                  for val in (glob.glob(path_pattern))])
    return ids

# Make sure that final_bins/ folder contains all bins in single folder for binIDs
# wildcard to work. Use extractProteinBins rule or perform manually.
binIDs = get_ids_from_path_pattern('final_bins/*.faa')
IDs = get_ids_from_path_pattern('assemblies/*')

DATA_READS = f'{config["path"]["root"]}/{config["folder"]["data"]}/{{IDs}}/{{IDs}}.fastq.gz'

# Inserting space here to avoid having to change the hardcoded line 22 edit in the metabagpipes parser to expand wildcards

rule all:
    input:
        expand(f'{config["path"]["root"]}/GTDBtk/{{IDs}}', IDs=IDs)
    message:
        """
        WARNING: Be very careful when adding/removing any lines above this message.
        The metaBAGpipes.sh parser is presently hardcoded to edit line 22 of this Snakefile to expand target rules accordingly,
        therefore adding/removing any lines before this message will likely result in parser malfunction.
        """
    shell:
        """
        echo {input}
        """


rule createFolders:
    input:
        config["path"]["root"]
    message:
        """
        Very simple rule to check that the metaBAGpipes.sh parser, Snakefile, and config.yaml file are set up correctly. 
        Generates folders from config.yaml config file, not strictly necessary to run this rule.
        """
    shell:
        """
        cd {input}
        echo -e "Setting up result folders in the following work directory: $(echo {input}) \n"

        # Generate folders.txt by extracting folder names from config.yaml file
        paste config.yaml |cut -d':' -f2|tail -n +4|head -n 18|sed '/^$/d' > folders.txt # NOTE: hardcoded number (18) for folder names, increase number if new folders are introduced.
        
        while read line;do 
            echo "Creating $line folder ... "
            mkdir -p $line;
        done < folders.txt
        
        echo -e "\nDone creating folders. \n"

        rm folders.txt
        """


rule downloadToy:
    input:
        f'{config["path"]["root"]}/{config["folder"]["scripts"]}/{config["scripts"]["toy"]}'
    message:
        """
        Downloads toy dataset into config.yaml data folder and organizes into sample-specific sub-folders.
        Requires download_toydata.txt to be present in scripts folder.
        Modify this rule to download a real dataset by replacing the links in the download_toydata.txt file with links to files from your dataset of intertest.
        """
    shell:
        """
        cd {config[path][root]}/{config[folder][data]}

        # Download each link in download_toydata.txt
        echo -e "\nBegin downloading toy dataset ... \n"
        while read line;do 
            wget $line;
        done < {input}
        echo -e "\nDone donwloading dataset.\n"
        
        # Rename downloaded files, this is only necessary for toy dataset (will cause error if used for real dataset)
        echo -ne "\nRenaming downloaded files ... "
        for file in *;do 
            mv $file ./$(echo $file|sed 's/?download=1//g');
        done
        echo -e " done. \n"

        # Organize data into sample specific sub-folders

        echo -ne "\nGenerating list of unique sample IDs ... "
        for file in *.gz; do 
            echo $file; 
        done | sed 's/_.*$//g' | sed 's/.fastq.gz//g' | uniq > ID_samples.txt
        echo -e " done.\n $(less ID_samples.txt|wc -l) samples identified.\n"

        echo -ne "\nOrganizing downloaded files into sample specific sub-folders ... "
        while read line; do 
            mkdir -p $line; 
            mv $line*.gz $line; 
        done < ID_samples.txt
        echo -e " done. \n"
        
        rm ID_samples.txt
        """


rule organizeData:
    input:
        f'{config["path"]["root"]}/{config["folder"]["data"]}'
    message:
        """
        Sorts paired end raw reads into sample specific sub folders within the dataset folder specified in the config.yaml file.
        Assumes all samples are present in abovementioned dataset folder.
        
        Note: This rule is meant to be run on real datasets. 
        Do not run for toy dataset, as downloadToy rule above sorts the downloaded data already.
        """
    shell:
        """
        cd {input}
    
        echo -ne "\nGenerating list of unique sample IDs ... "

        # Create list of unique sample IDs
        for file in *.gz; do 
            echo $file; 
        done | sed 's/_.*$//g' | sed 's/.fastq.gz//g' | uniq > ID_samples.txt

        echo -e " done.\n $(less ID_samples.txt|wc -l) samples identified.\n"

        # Create folder and move corresponding files for each sample

        echo -ne "\nOrganizing dataset into sample specific sub-folders ... "
        while read line; do 
            mkdir -p $line; 
            mv $line*.gz $line; 
        done < ID_samples.txt
        echo -e " done. \n"
        
        rm ID_samples.txt
        """


rule qfilter: 
    input:
        READS = DATA_READS
    output:
        f'{config["path"]["root"]}/{config["folder"]["qfiltered"]}/{{IDs}}/{{IDs}}.fastq.gz', 
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;

        mkdir -p $(dirname $(dirname {output}))
        mkdir -p $(dirname {output})

        fastp --thread {config[cores][fastp]} \
            -i {input} \
            -o {output} \
            -j $(dirname {output})/$(echo $(basename $(dirname {output}))).json \
            -h $(dirname {output})/$(echo $(basename $(dirname {output}))).html

        """


rule qfilterVis:
    input: 
        f'{config["path"]["root"]}/{config["folder"]["qfiltered"]}'
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/qfilter.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/qfilterVis.pdf'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        mkdir -p $(dirname {output.text})
        cd {input}

        echo -e "\nGenerating quality filtering results file qfilter.stats: ... "
        for folder in */;do
            for file in $folder*json;do
                ID=$(echo $file|sed 's|/.*$||g')
                readsBF=$(head -n 25 $file|grep total_reads|cut -d ':' -f2|sed 's/,//g'|head -n 1)
                readsAF=$(head -n 25 $file|grep total_reads|cut -d ':' -f2|sed 's/,//g'|tail -n 1)
                basesBF=$(head -n 25 $file|grep total_bases|cut -d ':' -f2|sed 's/,//g'|head -n 1)
                basesAF=$(head -n 25 $file|grep total_bases|cut -d ':' -f2|sed 's/,//g'|tail -n 1)
                q20BF=$(head -n 25 $file|grep q20_rate|cut -d ':' -f2|sed 's/,//g'|head -n 1)
                q20AF=$(head -n 25 $file|grep q20_rate|cut -d ':' -f2|sed 's/,//g'|tail -n 1)
                q30BF=$(head -n 25 $file|grep q30_rate|cut -d ':' -f2|sed 's/,//g'|head -n 1)
                q30AF=$(head -n 25 $file|grep q30_rate|cut -d ':' -f2|sed 's/,//g'|tail -n 1)
                percent=$(awk -v RBF="$readsBF" -v RAF="$readsAF" 'BEGIN{{print RAF/RBF}}' )
                echo "$ID $readsBF $readsAF $basesBF $basesAF $percent $q20BF $q20AF $q30BF $q30AF" >> qfilter.stats
                echo "Sample $ID retained $percent * 100 % of reads ... "
            done
        done

        echo "Done summarizing quality filtering results ... \nMoving to /stats/ folder and running plotting script ... "
        mv qfilter.stats {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}

        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][qfilterVis]}
        echo "Done. "
        rm Rplots.pdf
        """


rule megahit:
    input:
        rules.qfilter.output
    output:
        f'{config["path"]["root"]}/{config["folder"]["assemblies"]}/{{IDs}}/contigs.fasta.gz'
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.megahit.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        cd $TMPDIR

        echo -n "Copying qfiltered reads to $TMPDIR ... "
        cp {input} $TMPDIR
        echo "done. "

        echo -n "Running megahit ... "
        megahit -t {config[cores][megahit]} \
            --verbose \
            -r $(basename {input}) \
            -o tmp;
        echo "done. "

        echo "Renaming assembly ... "
        mv tmp/final.contigs.fa contigs.fasta
        
        echo "Fixing contig header names: replacing spaces with hyphens ... "
        sed -i 's/ /-/g' contigs.fasta

        echo "Zipping and moving assembly ... "
        gzip contigs.fasta
        mkdir -p $(dirname {output})
        mv contigs.fasta.gz $(dirname {output})
        echo "Done. "
        """


rule assemblyVis:
    input: 
        f'{config["path"]["root"]}/{config["folder"]["assemblies"]}'
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/assembly.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/assemblyVis.pdf',
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        mkdir -p $(dirname {output.text})
        cd {input}
    
        echo -e "\nGenerating assembly results file assembly.stats: ... "
        for folder in */;do
            for file in $folder*.gz;do
                ID=$(echo $file|sed 's|/contigs.fasta.gz||g')
                N=$(less $file|grep -c ">");
                L=$(less $file|grep ">"|cut -d '-' -f4|sed 's/len=//'|awk '{{sum+=$1}}END{{print sum}}');
                T=$(less $file|grep ">"|cut -d '-' -f4|sed 's/len=//'|awk '$1>=1000{{c++}} END{{print c+0}}');
                S=$(less $file|grep ">"|cut -d '-' -f4|sed 's/len=//'|awk '$1>=1000'|awk '{{sum+=$1}}END{{print sum}}');
                echo $ID $N $L $T $S>> assembly.stats;
                echo -e "Sample $ID has a total of $L bp across $N contigs, with $S bp present in $T contigs >= 1000 bp ... "
            done;
        done

        echo "Done summarizing assembly results ... \nMoving to /stats/ folder and running plotting script ... "
        mv assembly.stats {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}

        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][assemblyVis]}
        echo "Done. "
        rm Rplots.pdf
        """


rule metabat:
    input:
        contigs = rules.megahit.output,
        READS = f'{config["path"]["root"]}/{config["folder"]["qfiltered"]}'
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["metabat"]}/{{IDs}}/{{IDs}}.metabat-bins')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.metabat.benchmark.txt'
    message:
        """
        Cross map all samples with bwa then use the output of this rule to create contig abundance/depth files 
        to be used for binning with metabat2 and maxbin2. After depth files are copied back to workspace and 
        metabat2 finishes we avoid the need to copy bam files back to workspace saving space as well as 
        reducing total nubmer of jobs to run.
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        cd $TMPDIR
        cp {input.contigs} .
        mkdir -p {output}

        # Define the focal sample ID, fsample: 
        # The one sample that all other samples will be mapped against mapping sample msampleID in for loop
        fsampleID=$(echo $(basename $(dirname {input.contigs})))
        echo -e "\nFocal sample: $fsampleID ... "

        echo "Renaming and unzipping assembly ... "
        mv $(basename {input.contigs}) $(echo $fsampleID|sed 's/$/.fa.gz/g')
        gunzip $(echo $fsampleID|sed 's/$/.fa.gz/g')

        echo -e "\nIndexing assembly ... "
        bwa index $fsampleID.fa
        
        for folder in {input.READS}/*;do 

                id=$(basename $folder)

                echo -e "\nCopying sample $id to be mapped againts the focal sample $fsampleID ..."
                cp $folder/*.gz .
                
                # Maybe I should be piping the lines below to reduce I/O ?

                echo -e "\nMapping sample to assembly ... "
                bwa mem -t {config[cores][metabat]} $fsampleID.fa *.fastq.gz > $id.sam
                
                echo -e "\nConverting SAM to BAM with samtools view ... " 
                samtools view -@ {config[cores][metabat]} -Sb $id.sam > $id.bam

                echo -e "\nSorting BAM file with samtools sort ... " 
                samtools sort -@ {config[cores][metabat]} -o $id.sort $id.bam

                echo -e "\nRunning jgi_summarize_bam_contig_depths script to generate contig abundance/depth file ... "
                jgi_summarize_bam_contig_depths --outputDepth $id.depth $id.sort

                echo -e "\nCopying depth file to workspace"
                mv $id.depth {output}

                echo -e "\nRemoving temporary files ... "
                rm *.fastq.gz *.sam *.bam

        done
        
        nSamples=$(ls {input.READS}|wc -l)
        echo -e "\nDone mapping focal sample $fsampleID agains $nSamples samples in dataset folder."

        echo -e "\nRunning jgi_summarize_bam_contig_depths for all sorted bam files ... "
        jgi_summarize_bam_contig_depths --outputDepth $id.all.depth *.sort

        echo -e "\nRunning metabat2 ... "
        metabat2 -i $fsampleID.fa -a $id.all.depth -o $fsampleID

        mv *.fa $id.all.depth $(dirname {output})

        """


rule maxbin:
    input:
        assembly = rules.megahit.output,
        depth = rules.metabat.output
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["maxbin"]}/{{IDs}}/{{IDs}}.maxbin-bins')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.maxbin.benchmark.txt'
    message:
        """
        Note that this rule uses of the output depth of metabat2 as an input to bin using maxbin2.
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        cp -r {input.assembly} {input.depth} $TMPDIR
        mkdir -p $(dirname $(dirname {output}))
        cd $TMPDIR

        echo -e "\nUnzipping assembly ... "
        gunzip contigs.fasta.gz

        echo -e "\nGenerating list of depth files based on metabat2 output ... "
        find $(basename {input.depth}) -name "*.depth" > abund.list
        
        echo -e "\nRunning maxbin2 ... "
        run_MaxBin.pl -contig contigs.fasta -out $(basename $(dirname {output})) -abund_list abund.list
        
        rm contigs.fasta *.gz

        mkdir $(basename {output})
        mkdir -p $(dirname {output})

        mv *.fasta $(basename {output})
        mv $(basename {output}) *.summary *.abundance $(dirname {output})
        """


rule concoct:
    input:
        contigs = rules.megahit.output,
        reads = f'{config["path"]["root"]}/{config["folder"]["qfiltered"]}'
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["concoct"]}/{{IDs}}/{{IDs}}.concoct-bins')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.concoct.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        mkdir -p $(dirname $(dirname {output}))

        fsampleID=$(echo $(basename $(dirname {input.contigs})))
        echo -e "\nCopying focal sample assembly $fsampleID to TMPDIR ... "

        cp {input.contigs} $TMPDIR
        cd $TMPDIR

        echo "Unzipping assembly ... "
        gunzip $(basename {input.contigs})

        echo -e "Done. \nCutting up contigs to 10kbp chunks (default), do not use this for mapping!"
        cut_up_fasta.py -c {config[params][cutfasta]} -o 0 -m contigs.fasta -b assembly_c10k.bed > assembly_c10k.fa
        
        echo -e "\nIndexing assembly of original contigs for mapping (not 10kbp chunks assembly file) ... "
        bwa index contigs.fasta

        echo -e "Done. \nPreparing to map focal sample against other samples ... "
        for folder in {input.reads}/*;do 

                id=$(basename $folder)
                echo -e "\nCopying sample $id to be mapped againts the focal sample $fsampleID ..."
                cp $folder/*.gz .
                
                # Maybe I should be piping the lines below to reduce I/O ?

                echo -e "\nMapping sample to assembly ... "
                bwa mem -t {config[cores][concoct]} contigs.fasta *.fastq.gz > $id.sam
                
                echo -e "\nConverting SAM to BAM with samtools view ... " 
                samtools view -@ {config[cores][concoct]} -Sb $id.sam > $id.bam

                echo -e "\nSorting BAM file with samtools sort ... " 
                samtools sort -@ {config[cores][concoct]} -o $id.sort $id.bam

                echo -e "\nIndexing sorted BAM file with samtools index ... " 
                samtools index $id.sort

                echo -e "\nRemoving temporary files ... "
                rm *.fastq.gz *.sam *.bam

        done

        echo -e "\nSummarizing sorted and indexed BAM files with concoct_coverage_table.py ... " 
        concoct_coverage_table.py assembly_c10k.bed *.sort > coverage_table.tsv

        echo -e "\nRunning CONCOCT ... "
        concoct --coverage_file coverage_table.tsv --composition_file assembly_c10k.fa \
            -b $(basename $(dirname {output})) \
            -t {config[cores][concoct]} \
            -c {config[params][concoct]}
            
        echo -e "\nMerging clustering results into original contigs with merge_cutup_clustering.py ... "
        merge_cutup_clustering.py $(basename $(dirname {output}))_clustering_gt1000.csv > $(basename $(dirname {output}))_clustering_merged.csv
        
        echo -e "\nExtracting bins ... "
        mkdir -p $(basename {output})
        extract_fasta_bins.py contigs.fasta $(basename $(dirname {output}))_clustering_merged.csv --output_path $(basename {output})
        
        mkdir -p $(dirname {output})
        mv $(basename {output}) *.txt *.csv $(dirname {output})
        """


rule binRefine:
    input:
        concoct = f'{config["path"]["root"]}/{config["folder"]["concoct"]}/{{IDs}}/{{IDs}}.concoct-bins',
        metabat = f'{config["path"]["root"]}/{config["folder"]["metabat"]}/{{IDs}}/{{IDs}}.metabat-bins',
        maxbin = f'{config["path"]["root"]}/{config["folder"]["maxbin"]}/{{IDs}}/{{IDs}}.maxbin-bins'
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["refined"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.binRefine.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metawrap]};set -u;
        mkdir -p $(dirname {output})
        mkdir -p {output}
        cd $TMPDIR

        echo "Copying bins from CONCOCT, metabat2, and maxbin2 to tmpdir ... "
        cp -r {input.concoct} {input.metabat} {input.maxbin} $TMPDIR

        echo "Renaming bin folders to avoid errors with metaWRAP ... "
        mv $(basename {input.concoct}) $(echo $(basename {input.concoct})|sed 's/-bins//g')
        mv $(basename {input.metabat}) $(echo $(basename {input.metabat})|sed 's/-bins//g')
        mv $(basename {input.maxbin}) $(echo $(basename {input.maxbin})|sed 's/-bins//g')
        
        echo "Running metaWRAP bin refinement module ... "
        metaWRAP bin_refinement -o . \
            -A $(echo $(basename {input.concoct})|sed 's/-bins//g') \
            -B $(echo $(basename {input.metabat})|sed 's/-bins//g') \
            -C $(echo $(basename {input.maxbin})|sed 's/-bins//g') \
            -t {config[cores][refine]} \
            -m {config[params][refineMem]} \
            -c {config[params][refineComp]} \
            -x {config[params][refineCont]}
 
        rm -r $(echo $(basename {input.concoct})|sed 's/-bins//g') $(echo $(basename {input.metabat})|sed 's/-bins//g') $(echo $(basename {input.maxbin})|sed 's/-bins//g') work_files
        mv * {output}
        """


rule binReassemble:
    input:
        READS = rules.qfilter.output,
        refinedBins = rules.binRefine.output
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["reassembled"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.binReassemble.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metawrap]};set -u;
        mkdir -p $(dirname {output})
        cp -r {input.refinedBins}/metawrap_*_bins {input.READS} $TMPDIR
        cd $TMPDIR
        
        echo "Running metaWRAP bin reassembly ... "
        metaWRAP reassemble_bins -o $(basename {output}) \
            -b metawrap_*_bins \
            -1 $(basename {input.READS}) \
            -2 $(basename {input.READS}) \
            -t {config[cores][reassemble]} \
            -m {config[params][reassembleMem]} \
            -c {config[params][reassembleComp]} \
            -x {config[params][reassembleCont]}
        
        rm -r metawrap_*_bins
        rm -r $(basename {output})/work_files
        rm *.fastq.gz 
        mv * $(dirname {output})
        """


rule binningVis:
    input: 
        f'{config["path"]["root"]}'
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/reassembled_bins.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/binningVis.pdf'
    message:
        """
        Generate bar plot with number of bins and density plot of bin contigs, 
        total length, completeness, and contamination across different tools.
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        
        # READ CONCOCT BINS

        echo "Generating concoct_bins.stats file containing bin ID, number of contigs, and length ... "
        cd {input}/{config[folder][concoct]}
        for folder in */;do 
            var=$(echo $folder|sed 's|/||g'); # Define sample name
            for bin in $folder*concoct-bins/*.fa;do 
                name=$(echo $bin | sed "s|^.*/|$var.bin.|g" | sed 's/.fa//g'); # Define bin name
                N=$(less $bin | grep -c ">");
                L=$(less $bin |grep ">"|cut -d '-' -f4|sed 's/len=//g'|awk '{{sum+=$1}}END{{print sum}}')
                echo "Reading bin $bin ... Contigs: $N , Length: $L "
                echo $name $N $L >> concoct_bins.stats;
            done;
        done
        mv *.stats {input}/{config[folder][reassembled]}
        echo "Done reading CONCOCT bins, moving concoct_bins.stats file to $(echo {input}/{config[folder][reassembled]}) ."

        # READ METABAT2 BINS

        echo "Generating metabat_bins.stats file containing bin ID, number of contigs, and length ... "
        cd {input}/{config[folder][metabat]}
        for folder in */;do 
            var=$(echo $folder | sed 's|/||'); # Define sample name
            for bin in $folder*metabat-bins/*.fa;do 
                name=$(echo $bin|sed 's/.fa//g'|sed 's|^.*/||g'|sed "s/^/$var./g"); # Define bin name
                N=$(less $bin | grep -c ">");
                L=$(less $bin |grep ">"|cut -d '-' -f4|sed 's/len=//g'|awk '{{sum+=$1}}END{{print sum}}')
                echo "Reading bin $bin ... Contigs: $N , Length: $L "
                echo $name $N $L >> metabat_bins.stats;
            done;
        done
        mv *.stats {input}/{config[folder][reassembled]}
        echo "Done reading metabat2 bins, moving metabat_bins.stats file to $(echo {input}/{config[folder][reassembled]}) ."

        # READ MAXBIN2 BINS

        echo "Generating maxbin_bins.stats file containing bin ID, number of contigs, and length ... "
        cd {input}/{config[folder][maxbin]}
        for folder in */;do
            for bin in $folder*maxbin-bins/*.fasta;do 
                name=$(echo $bin | sed 's/.fasta//g' | sed 's|^.*/||g');  # Define bin name
                N=$(less $bin | grep -c ">");
                L=$(less $bin |grep ">"|cut -d '-' -f4|sed 's/len=//g'|awk '{{sum+=$1}}END{{print sum}}')
                echo "Reading bin $bin ... Contigs: $N , Length: $L "
                echo $name $N $L >> maxbin_bins.stats;
            done;
        done
        mv *.stats {input}/{config[folder][reassembled]}
        echo "Done reading maxbin2 bins, moving maxbin_bins.stats file to $(echo {input}/{config[folder][reassembled]}) ."

        # READ METAWRAP REFINED BINS

        echo "Generating refined_bins.stats file containing bin ID, number of contigs, and length ... "
        cd {input}/{config[folder][refined]}
        for folder in */;do 
            samp=$(echo $folder | sed 's|/||'); # Define sample name 
            for bin in $folder*metawrap_*_bins/*.fa;do 
                name=$(echo $bin | sed 's/.fa//g'|sed 's|^.*/||g'|sed "s/^/$samp./g"); # Define bin name
                N=$(less $bin | grep -c ">");
                L=$(less $bin |grep ">"|cut -d '-' -f4|sed 's/len_//g'|awk '{{sum+=$1}}END{{print sum}}')
                echo "Reading bin $bin ... Contigs: $N , Length: $L "
                echo $name $N $L >> refined_bins.stats;
            done;
        done
        echo "Done reading metawrap refined bins ... "

        # READ METAWRAP REFINED CHECKM OUTPUT        
        
        echo "Generating CheckM summary files across samples: concoct.checkm, metabat.checkm, maxbin.checkm, and refined.checkm ... "
        for folder in */;do 
            var=$(echo $folder|sed 's|/||g'); # Define sample name
            paste $folder*concoct.stats|tail -n +2 | sed "s/^/$var.bin./g" >> concoct.checkm
            paste $folder*metabat.stats|tail -n +2 | sed "s/^/$var./g" >> metabat.checkm
            paste $folder*maxbin.stats|tail -n +2 >> maxbin.checkm
            paste $folder*metawrap_*_bins.stats|tail -n +2|sed "s/^/$var./g" >> refined.checkm
        done 
        echo "Done reading metawrap refined output, moving refined_bins.stats, concoct.checkm, metabat.checkm, maxbin.checkm, and refined.checkm files to $(echo {input}/{config[folder][reassembled]}) ."
        mv *.stats *.checkm {input}/{config[folder][reassembled]}

        # READ METAWRAP REASSEMBLED BINS

        echo "Generating reassembled_bins.stats file containing bin ID, number of contigs, and length ... "
        cd {input}/{config[folder][reassembled]}
        for folder in */;do 
            samp=$(echo $folder | sed 's|/||'); # Define sample name 
            for bin in $folder*reassembled_bins/*.fa;do 
                name=$(echo $bin | sed 's/.fa//g' | sed 's|^.*/||g' | sed "s/^/$samp./g"); # Define bin name
                N=$(less $bin | grep -c ">");

                # Need to check if bins are original (megahit-assembled) or strict/permissive (metaspades-assembled)
                if [[ $name == *.strict ]] || [[ $name == *.permissive ]];then
                    L=$(less $bin |grep ">"|cut -d '_' -f4|awk '{{sum+=$1}}END{{print sum}}')
                else
                    L=$(less $bin |grep ">"|cut -d '-' -f4|sed 's/len_//g'|awk '{{sum+=$1}}END{{print sum}}')
                fi

                echo "Reading bin $bin ... Contigs: $N , Length: $L "
                echo $name $N $L >> reassembled_bins.stats;
            done;
        done
        echo "Done reading metawrap reassembled bins ... "

        # READ METAWRAP REFINED CHECKM OUTPUT  

        echo "Generating CheckM summary file reassembled.checkm across samples for reassembled bins ... "
        for folder in */;do 
            var=$(echo $folder|sed 's|/||g');
            paste $folder*reassembled_bins.stats|tail -n +2|sed "s/^/$var./g";
        done >> reassembled.checkm
        echo "Done generating all statistics files for binning results ... running plotting script ... "

        # RUN PLOTTING R SCRIPT

        mv *.stats *.checkm {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}

        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][binningVis]}
        rm Rplots.pdf # Delete redundant pdf file
        echo "Done. "
        """

rule GTDBtk:
    input: 
        f'{config["path"]["root"]}/{config["folder"]["reassembled"]}/{{IDs}}/reassembled_bins'
    output:
        directory(f'{config["path"]["root"]}/GTDBtk/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.GTDBtk.benchmark.txt'
    message:
        """
        The folder dna_bins_organized assumes subfolders containing dna bins for refined and reassembled bins.
        Note: slightly modified inputs/outputs for european dataset.
        """
    shell:
        """
        set +u;source activate gtdbtk-tmp;set -u;
        export GTDBTK_DATA_PATH=/g/scb2/patil/zorrilla/conda/envs/gtdbtk/share/gtdbtk-1.1.0/db/

        cd $SCRATCHDIR
        cp -r {input} .

        gtdbtk classify_wf --genome_dir $(basename {input}) --out_dir GTDBtk -x fa --cpus {config[cores][gtdbtk]}
        mkdir -p {output}
        mv GTDBtk/* {output}

        """

rule classifyGenomes:
    input:
        bins = f'{config["path"]["root"]}/{config["folder"]["reassembled"]}/{{IDs}}/reassembled_bins',
        script = f'{config["path"]["root"]}/{config["folder"]["scripts"]}/classify-genomes'
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["classification"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.classify-genomes.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        mkdir -p {output}
        cd $TMPDIR
        cp -r {input.script}/* {input.bins}/* .

        echo "Begin classifying bins ... "
        for bin in *.fa; do
            echo -e "\nClassifying $bin ... "
            $PWD/classify-genomes $bin -t {config[cores][classify]} -o $(echo $bin|sed 's/.fa/.taxonomy/')
            cp *.taxonomy {output}
            rm *.taxonomy
            rm $bin 
        done
        echo "Done classifying bins. "
        """


rule taxonomyVis:
    input: 
        f'{config["path"]["root"]}/{config["folder"]["classification"]}'
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/classification.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/taxonomyVis.pdf'
    message:
        """
        Generate bar plot with most common taxa (n>15) and density plots with mapping statistics.
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        cd {input}

        echo -e "\nBegin reading classification result files ... \n"
        for folder in */;do 

            for file in $folder*.taxonomy;do

                # Define sample ID to append to start of each bin name in summary file
                sample=$(echo $folder|sed 's|/||')

                # Define bin name with sample ID, shorten metaWRAP naming scheme (orig/permissive/strict)
                fasta=$(echo $file | sed 's|^.*/||' | sed 's/.taxonomy//g' | sed 's/orig/o/g' | sed 's/permissive/p/g' | sed 's/strict/s/g' | sed "s/^/$sample./g");

                # Extract NCBI ID 
                NCBI=$(less $file | grep NCBI | cut -d ' ' -f4);

                # Extract consensus taxonomy
                tax=$(less $file | grep tax | sed 's/Consensus taxonomy: //g');

                # Extract consensus motus
                motu=$(less $file | grep mOTUs | sed 's/Consensus mOTUs: //g');

                # Extract number of detected genes
                detect=$(less $file | grep detected | sed 's/Number of detected genes: //g');

                # Extract percentage of agreeing genes
                percent=$(less $file | grep agreeing | sed 's/Percentage of agreeing genes: //g' | sed 's/%//g');

                # Extract number of mapped genes
                map=$(less $file | grep mapped | sed 's/Number of mapped genes: //g');
                
                # Extract COG IDs, need to use set +e;...;set -e to avoid erroring out when reading .taxonomy result file for bin with no taxonomic annotation
                set +e
                cog=$(less $file | grep COG | cut -d$'\t' -f1 | tr '\n' ',' | sed 's/,$//g');
                set -e
                
                # Display and store extracted results
                echo -e "$fasta \t $NCBI \t $tax \t $motu \t $detect \t $map \t $percent \t $cog"
                echo -e "$fasta \t $NCBI \t $tax \t $motu \t $detect \t $map \t $percent \t $cog" >> classification.stats;
            
            done;
        
        done

        echo -e "\nDone generating classification.stats summary file, moving to stats/ directory and running taxonomyVis.R script ... "
        mv classification.stats {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}

        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][taxonomyVis]}
        rm Rplots.pdf # Delete redundant pdf file
        echo "Done. "
        """


rule abundance:
    input:
        bins = f'{config["path"]["root"]}/{config["folder"]["reassembled"]}/{{IDs}}/reassembled_bins',
        READS = rules.qfilter.output
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["abundance"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.abundance.benchmark.txt'
    message:
        """
        Calculate bin abundance fraction using the following:

        binAbundanceFraction = ( X / Y / Z) * 1000000

        X = # of reads mapped to bin_i from sample_k
        Y = length of bin_i (bp)
        Z = # of reads mapped to all bins in sample_k

        Note: 1000000 scaling factor converts length in bp to Mbp

        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        mkdir -p {output}
        cd $TMPDIR

        echo -e "\nCopying quality filtered single end reads and generated MAGs to TMPDIR ... "
        cp {input.READS} {input.bins}/* .

        echo -e "\nConcatenating all bins into one FASTA file ... "
        cat *.fa > $(basename {output}).fa

        echo -e "\nCreating bwa index for concatenated FASTA file ... "
        bwa index $(basename {output}).fa

        echo -e "\nMapping quality filtered single end reads to concatenated FASTA file with bwa mem ... "
        bwa mem -t {config[cores][abundance]} $(basename {output}).fa \
            $(basename {input.READS}) > $(basename {output}).sam

        echo -e "\nConverting SAM to BAM with samtools view ... "
        samtools view -@ {config[cores][abundance]} -Sb $(basename {output}).sam > $(basename {output}).bam

        echo -e "\nSorting BAM file with samtools sort ... "
        samtools sort -@ {config[cores][abundance]} -o $(basename {output}).sort.bam $(basename {output}).bam

        echo -e "\nExtracting stats from sorted BAM file with samtools flagstat ... "
        samtools flagstat $(basename {output}).sort.bam > map.stats

        echo -e "\nCopying sample_map.stats file to root/abundance/sample for bin concatenation and deleting temporary FASTA file ... "
        cp map.stats {output}/$(basename {output})_map.stats
        rm $(basename {output}).fa
        
        echo -e "\nRepeat procedure for each bin ... "
        for bin in *.fa;do

            echo -e "\nSetting up temporary sub-directory to map against bin $bin ... "
            mkdir -p $(echo "$bin"| sed "s/.fa//")
            mv $bin $(echo "$bin"| sed "s/.fa//")
            cd $(echo "$bin"| sed "s/.fa//")

            echo -e "\nCreating bwa index for bin $bin ... "
            bwa index $bin

            echo -e "\nMapping quality filtered single end reads to bin $bin with bwa mem ... "
            bwa mem -t {config[cores][abundance]} $bin ../$(basename {input.READS}) > $(echo "$bin"|sed "s/.fa/.sam/")

            echo -e "\nConverting SAM to BAM with samtools view ... "
            samtools view -@ {config[cores][abundance]} -Sb $(echo "$bin"|sed "s/.fa/.sam/") > $(echo "$bin"|sed "s/.fa/.bam/")

            echo -e "\nSorting BAM file with samtools sort ... "
            samtools sort -@ {config[cores][abundance]} -o $(echo "$bin"|sed "s/.fa/.sort.bam/") $(echo "$bin"|sed "s/.fa/.bam/")

            echo -e "\nExtracting stats from sorted BAM file with samtools flagstat ... "
            samtools flagstat $(echo "$bin"|sed "s/.fa/.sort.bam/") > $(echo "$bin"|sed "s/.fa/.map/")

            echo -e "\nAppending bin length to bin.map stats file ... "
            echo -n "Bin Length = " >> $(echo "$bin"|sed "s/.fa/.map/")

            # Need to check if bins are original (megahit-assembled) or strict/permissive (metaspades-assembled)
            if [[ $bin == *.strict.fa ]] || [[ $bin == *.permissive.fa ]];then
                less $bin |grep ">"|cut -d '_' -f4|awk '{{sum+=$1}}END{{print sum}}' >> $(echo "$bin"|sed "s/.fa/.map/")
            else
                less $bin |grep ">"|cut -d '-' -f4|sed 's/len_//g'|awk '{{sum+=$1}}END{{print sum}}' >> $(echo "$bin"|sed "s/.fa/.map/")
            fi

            paste $(echo "$bin"|sed "s/.fa/.map/")

            echo -e "\nCalculating abundance for bin $bin ... "
            echo -n "$bin"|sed "s/.fa//" >> $(echo "$bin"|sed "s/.fa/.abund/")
            echo -n $'\t' >> $(echo "$bin"|sed "s/.fa/.abund/")

            X=$(less $(echo "$bin"|sed "s/.fa/.map/")|grep "mapped ("|awk -F' ' '{{print $1}}')
            Y=$(less $(echo "$bin"|sed "s/.fa/.map/")|tail -n 1|awk -F' ' '{{print $4}}')
            Z=$(less "../map.stats"|grep "mapped ("|awk -F' ' '{{print $1}}')
            awk -v x="$X" -v y="$Y" -v z="$Z" 'BEGIN{{print (x/y/z) * 1000000}}' >> $(echo "$bin"|sed "s/.fa/.abund/")
            
            paste $(echo "$bin"|sed "s/.fa/.abund/")
            
            echo -e "\nRemoving temporary files for bin $bin ... "
            rm $bin
            cp $(echo "$bin"|sed "s/.fa/.map/") {output}
            mv $(echo "$bin"|sed "s/.fa/.abund/") ../
            cd ..
            rm -r $(echo "$bin"| sed "s/.fa//")
        done

        echo -e "\nDone processing all bins, summarizing results into sample.abund file ... "
        cat *.abund > $(basename {output}).abund

        echo -ne "\nSumming calculated abundances to obtain normalization value ... "
        norm=$(less $(basename {output}).abund |awk '{{sum+=$2}}END{{print sum}}');
        echo $norm

        echo -e "\nGenerating column with abundances normalized between 0 and 1 ... "
        awk -v NORM="$norm" '{{printf $1"\t"$2"\t"$2/NORM"\\n"}}' $(basename {output}).abund > abundance.txt

        rm $(basename {output}).abund
        mv abundance.txt $(basename {output}).abund

        mv $(basename {output}).abund {output}
        """

rule abundanceVis:
    input:
        abundance = f'{config["path"]["root"]}/{config["folder"]["abundance"]}',
        taxonomy = rules.taxonomyVis.output.text
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/abundance.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/abundanceVis.pdf'
    message:
        """
        Generate stacked bar plots showing composition of samples
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u
        cd {input.abundance}

        for folder in */;do

            # Define sample ID
            sample=$(echo $folder|sed 's|/||g')
            
            # Same as in taxonomyVis rule, modify bin names by adding sample ID and shortening metaWRAP naming scheme (orig/permissive/strict)
            paste $sample/$sample.abund | sed 's/orig/o/g' | sed 's/permissive/p/g' | sed 's/strict/s/g' | sed "s/^/$sample./g" >> abundance.stats
       
        done

        mv abundance.stats {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}
        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][abundanceVis]}

        """


rule extractProteinBins:
    message:
        "Extract ORF annotated protein fasta files for each bin from reassembly checkm files."
    shell:
        """
        cd {config[path][root]}
        mkdir -p {config[folder][proteinBins]}

        echo -e "Begin moving and renaming ORF annotated protein fasta bins from reassembled_bins/ to final_bins/ ... \n"
        for folder in reassembled_bins/*/;do 
            echo "Moving bins from sample $(echo $(basename $folder)) ... "
            for bin in $folder*reassembled_bins.checkm/bins/*;do 
                var=$(echo $bin/genes.faa | sed 's|reassembled_bins/||g'|sed 's|/reassembled_bins.checkm/bins||'|sed 's|/genes||g'|sed 's|/|_|g'|sed 's/permissive/p/g'|sed 's/orig/o/g'|sed 's/strict/s/g');
                cp $bin/*.faa {config[path][root]}/{config[folder][proteinBins]}/$var;
            done;
        done
        """


rule carveme:
    input:
        bin = f'{config["path"]["root"]}/{config["folder"]["proteinBins"]}/{{binIDs}}.faa',
        media = f'{config["path"]["root"]}/{config["folder"]["scripts"]}/{config["scripts"]["carveme"]}'
    output:
        f'{config["path"]["root"]}/{config["folder"]["GEMs"]}/{{binIDs}}.xml'
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{binIDs}}.carveme.benchmark.txt'
    message:
        """
        Make sure that the input files are ORF annotated and preferably protein fasta.
        If given raw fasta files, Carveme will run without errors but each contig will be treated as one gene.
        """
    shell:
        """
        echo "Activating {config[envs][metabagpipes]} conda environment ... "
        set +u;source activate {config[envs][metabagpipes]};set -u
        
        mkdir -p $(dirname {output})
        mkdir -p logs

        cp {input.bin} {input.media} $TMPDIR
        cd $TMPDIR
        
        echo "Begin carving GEM ... "
        #carve -g {config[params][carveMedia]} \
        #    -v \
        #    --mediadb $(basename {input.media}) \
        #    --fbc2 \
        #    -o $(echo $(basename {input.bin}) | sed 's/.faa/.xml/g') $(basename {input.bin})

        carve -v \
            --fbc2 \
            -o $(echo $(basename {input.bin}) | sed 's/.faa/.xml/g') $(basename {input.bin})
        
        echo "Done carving GEM. "
        [ -f *.xml ] && mv *.xml $(dirname {output})
        """


rule modelVis:
    input: 
        f'{config["path"]["root"]}/{config["folder"]["GEMs"]}'
    output: 
        text = f'{config["path"]["root"]}/{config["folder"]["stats"]}/GEMs.stats',
        plot = f'{config["path"]["root"]}/{config["folder"]["stats"]}/modelVis.pdf'
    message:
        """
        Generate bar plot with GEMs generated across samples and density plots showing number of 
        unique metabolites, reactions, and genes across GEMs.
        """
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u;
        cd {input}

        echo -e "\nBegin reading models ... \n"
        for model in *.xml;do 
            id=$(echo $model|sed 's/.xml//g'); 
            mets=$(less $model| grep "species id="|cut -d ' ' -f 8|sed 's/..$//g'|sort|uniq|wc -l);
            rxns=$(less $model|grep -c 'reaction id=');
            genes=$(less $model|grep 'fbc:geneProduct fbc:id='|grep -vic spontaneous);
            echo "Model: $id has $mets mets, $rxns reactions, and $genes genes ... "
            echo "$id $mets $rxns $genes" >> GEMs.stats;
        done

        echo -e "\nDone generating GEMs.stats summary file, moving to stats/ folder and running modelVis.R script ... "
        mv GEMs.stats {config[path][root]}/{config[folder][stats]}
        cd {config[path][root]}/{config[folder][stats]}

        Rscript {config[path][root]}/{config[folder][scripts]}/{config[scripts][modelVis]}
        rm Rplots.pdf # Delete redundant pdf file
        echo "Done. "
        """


rule organizeGEMs:
    input:
        f'{config["path"]["root"]}/{config["folder"]["refined"]}'
    message:
        """
        Organizes GEMs into sample specific subfolders. 
        Necessary to run smetana per sample using the IDs wildcard.
        """
    shell:
        """
        cd {input}
        for folder in */;do
            echo -n "Creating GEM subfolder for sample $folder ... "
            mkdir -p ../{config[folder][GEMs]}/$folder;
            echo -n "moving GEMs ... "
            mv ../{config[folder][GEMs]}/$(echo $folder|sed 's|/||')_*.xml ../{config[folder][GEMs]}/$folder;
            echo "done. "
        done
        """

rule memote:
    input:
        f'{config["path"]["root"]}/{config["folder"]["GEMs"]}/{{IDs}}'
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["memote"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.memote.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u

        mkdir -p $(dirname {output})
        mkdir -p {output}
        
        cp {input}/*.xml $TMPDIR
        cd $TMPDIR
        
        for model in *.xml;do
            memote report snapshot --filename $(echo $model|sed 's/.xml/.html/') $model
            memote run $model > $(echo $model|sed 's/.xml/-summary.txt/')
            mv *.txt *.html {output}
            rm $model
        done
        """

rule smetana:
    input:
        f'{config["path"]["root"]}/{config["folder"]["GEMs"]}/{{IDs}}'
    output:
        f'{config["path"]["root"]}/{config["folder"]["SMETANA"]}/{{IDs}}_detailed.tsv'
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.smetana.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u
        mkdir -p {config[path][root]}/{config[folder][SMETANA]}
        cp {config[path][root]}/{config[folder][scripts]}/{config[scripts][carveme]} {input}/*.xml $TMPDIR
        cd $TMPDIR
        
        smetana -o $(basename {input}) --flavor fbc2 \
            --mediadb media_db.tsv -m {config[params][smetanaMedia]} \
            --detailed \
            --solver {config[params][smetanaSolver]} -v *.xml
        
        mv *.tsv $(dirname {output})
        """

rule motus2:
    input: 
        rules.qfilter.output
    output:
        directory(f'{config["path"]["root"]}/test/motus2/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.motus2.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u
        cp {input} $TMPDIR
        cd $TMPDIR

        motus profile -s $(basename {input}) -o $(basename {input}).motus2 -t 12
        mkdir -p {output}
        rm $(basename {input})
        mv * {output}
        """

rule grid:
    input:
        bins = f'{config["path"]["root"]}/{config["folder"]["reassembled"]}/{{IDs}}/reassembled_bins',
        reads = rules.qfilter.output
    output:
        directory(f'{config["path"]["root"]}/{config["folder"]["GRiD"]}/{{IDs}}')
    benchmark:
        f'{config["path"]["root"]}/benchmarks/{{IDs}}.grid.benchmark.txt'
    shell:
        """
        set +u;source activate {config[envs][metabagpipes]};set -u

        cp -r {input.bins} {input.reads} $TMPDIR
        cd $TMPDIR

        mkdir MAGdb out
        update_database -d MAGdb -g $(basename {input.bins}) -p MAGdb
        rm -r $(basename {input.bins})

        grid multiplex -r . -e fastq.gz -d MAGdb -p -c 0.2 -o out -n {config[cores][grid]}

        rm $(basename {input.reads})
        mkdir {output}
        mv out/* {output}
        """
