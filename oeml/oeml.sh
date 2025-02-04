#!/bin/bash

DATA_DIR=$1
EXP_DIR=$2
NUM_SNAPS=$3
DELTA_TT=$4
DELTA_FC=$5
CHANGE=$6
IN_ALL_SNAPS=$7
SUB_PROP=$8
IN_PROP=$9
LABEL_PROP=${10}
PARTIAL_TREE=${11}

python2 genFeatsP.py -i $DATA_DIR -o $EXP_DIR -n $NUM_SNAPS -dtt $DELTA_TT -dfc $DELTA_FC -c $CHANGE -s $SUB_PROP -m $IN_PROP -l $LABEL_PROP -f nt $PARTIAL_TREE 2> $EXP_DIR/error.txt > $EXP_DIR/feats_out.txt
Rscript identity-aggregator-p.R $EXP_DIR/feats*.csv $EXP_DIR/training.csv $EXP_DIR/evaluation.csv $IN_ALL_SNAPS 2>> $EXP_DIR/error.txt > $EXP_DIR/identity_out.txt
./weka-batch.sh $EXP_DIR/training.csv $EXP_DIR/evaluation.csv $EXP_DIR/temp.model $EXP_DIR/results.txt 2>> $EXP_DIR/error.txt > $EXP_DIR/weka_out.txt

exit 0
