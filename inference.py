import os
import wandb
import torch
import random
import importlib
import numpy as np
import pandas as pd 
from datasets import Dataset
from model import RobertaForSimilarityClassification
from utils.encoder import Encoder
from utils.collator import DataCollatorWithPadding
from utils.preprocessor import Preprocessor
from tqdm import tqdm

from arguments import (ModelArguments, 
    DataTrainingArguments, 
    MyTrainingArguments, 
    InferenceArguments
)

from transformers import (
    AutoConfig,
    AutoTokenizer,
    HfArgumentParser,
    Trainer,
)

def main():
    parser = HfArgumentParser(
        (ModelArguments, DataTrainingArguments, MyTrainingArguments, InferenceArguments)
    )
    model_args, data_args, training_args, inference_args = parser.parse_args_into_dataclasses()

    # -- Loading datasets
    df = pd.read_csv(os.path.join(data_args.date_path, 'test.csv'))
    
    # -- Preprocessing datasets
    preprocessor = Preprocessor()
    df['code1'] = df['code1'].apply(preprocessor)
    df['code2'] = df['code2'].apply(preprocessor)
    dset = Dataset.from_pandas(df)
    print(dset)

    # -- Tokenizing & Encoding
    tokenizer = AutoTokenizer.from_pretrained(inference_args.ORG_PLM)
    encoder = Encoder(tokenizer, data_args.max_length)
    dset = dset.map(encoder, batched=True, num_proc=4, remove_columns=dset.column_names)
    print(dset)

    # -- Model Class
    model_class = RobertaForSimilarityClassification
    
    # -- Collator
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer, max_length=data_args.max_length)
    
    pred_probs = []
    for i in tqdm(range(training_args.fold_size)) :
        PLM = os.path.join(model_args.PLM, f'fold{i}')

        # -- Config & Model
        config = AutoConfig.from_pretrained(PLM)
        model = model_class(model_checkpoint=inference_args.ORG_PLM, config=config)
        model.load_state_dict(torch.load(os.path.join(PLM, 'pytorch_model.bin')))

        trainer = Trainer(                       # the instantiated 🤗 Transformers model to be trained
            model=model,                         # trained model
            args=training_args,                  # training arguments, defined above
            data_collator=data_collator,         # collator
        )

        # -- Inference
        outputs = trainer.predict(dset)
        pred_probs.append(outputs[0])

    pred = np.mean(pred_probs, axis=0)
    pred_ids = np.where(pred >= 0.5, 1, 0)
    sub_df = pd.read_csv(os.path.join(data_args.date_path, 'sample_submission.csv'))
    sub_df['similar'] = pred_ids
    sub_df.to_csv(os.path.join(inference_args.dir_path, 'soft_voting.csv'))

   
if __name__ == "__main__" :
    main()