import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter
from datetime import datetime
  
#Define focal loss    
def focal(outputs,targets,gamma=2):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    #Dictionary used to make alpha
    label_to_distribution = {0: 1-0.455, 1: 1-0.015, 2: 1-0.227, 3: 1-0.136, 4: 1-0.166}
    #Get cross-entropy loss
    ce_loss = F.cross_entropy(outputs, targets, reduction='none') # important to add reduction='none' to keep per-batch-item loss
    pt = torch.exp(-ce_loss)
    #create alpha
    alpha = torch.ones(len(targets))
    for i,label in enumerate(targets):
        alpha[i] = alpha[i]*label_to_distribution[label.item()]
    alpha = alpha.to(device)
    focal_loss = (alpha * (1-pt)**gamma * ce_loss).mean() # mean over the batch
    return focal_loss
    
#Define the training as a function.
def train(model, optimizer, scheduler, train_loader, test_loader, device, loss_function="crossentropy", seed=42, batch_size='128', num_epochs=1, model_choice='ConvNet', n_features=16, height=256, width=128, droprate=0.5, lr=0.1, num_blocks=3, r='r', weighted=1, transform=1, intensity=1,intensity_type="image",final=False):
    if loss_function == "focal":
        lf = focal
        print("using focal loss")
    elif loss_function == "crossentropy":
        lf = F.cross_entropy
        print("using cross-entropy loss")
    else:
        sys.exit("The chosen loss function isn't valid")
    classes = train_loader.dataset.get_image_classes()
    
    writer = SummaryWriter(log_dir="../logs/" + 
    datetime.today().strftime('%d-%m-%y:%H%M') +
    f' {model_choice} {loss_function} blocks={num_blocks} features={n_features} height={height} width={width} weighted={weighted} transform={transform} intensity={intensity}')
    
    for epoch in range(num_epochs):
        print(epoch+1)
        model.train()
        #For each epoch
        train_correct = 0
        for minibatch_no, (data, target, scaler) in enumerate(train_loader):
            data, target, scaler = data.to(device), target.to(device), scaler.to(device)
            #Zero the gradients computed for each weight
            optimizer.zero_grad()
            #Forward pass your image through the network
            if model_choice == "ConvNetScale":
                output = model(data,scaler)
            else:
                output = model(data)
            #Compute the loss
            loss = lf(output,target)
            #Backward pass through the network
            loss.backward()
            #Update the weights
            optimizer.step()
            
            #Compute how many were correctly classified
            predicted = output.argmax(1)
            train_correct += (target==predicted).sum().cpu().item()
            
            #Remove mini-batch from memory
            del data, target, loss
        if not final: 
            #Comput the test accuracy
            test_correct = 0
            model.eval()
            class_correct = list(0. for i in range(len(classes)))
            class_total = list(0. for i in range(len(classes)))
            for data, target,scaler in test_loader:
                data, scaler = data.to(device), scaler.to(device)
                with torch.no_grad():
                    if model_choice == "ConvNetScale":
                        output = model(data,scaler)
                    else:
                        output = model(data)
                predicted = output.argmax(1).cpu()

                test_correct += (target == predicted).sum().item()

                c = (predicted == target).squeeze()
                for i in range(data.shape[0]):
                    label = target[i]
                    class_correct[label] += c[i].item()
                    class_total[label] += 1

            scheduler.step()

            for i in range(len(classes)):
                print('Accuracy of %5s : %2d %%' % (classes[i], 100 * class_correct[i] / class_total[i]))            

            Barley_Acc = 100 * class_correct[0] / class_total[0]
            Broken_Acc = 100 * class_correct[1] / class_total[1]
            Oat_Acc = 100 * class_correct[2] / class_total[2]
            Rye_Acc = 100 * class_correct[3] / class_total[3]
            Wheat_Acc = 100 * class_correct[4] / class_total[4]

            train_acc = train_correct/len(train_loader.dataset)
            test_acc = test_correct/len(test_loader.dataset)
            writer.add_scalars('Train_Test_Accuracies', {'Train_Accuracy':train_acc, 'Test_Accuracy':test_acc}, epoch)
            writer.add_scalars('Class_Accuracies', {'Barley':Barley_Acc, 'Broken':Broken_Acc, 'Oat':Oat_Acc, 'Rye':Rye_Acc, 'Wheat':Wheat_Acc}, epoch)


            print("Accuracy train: {train:.1f}%\t test: {test:.1f}%".format(test=100*test_acc, train=100*train_acc))
        
    writer.add_hparams({'Batch_Size':batch_size, 'Epochs':num_epochs, 'Model':model_choice, 'Loss function':loss_function, 'Features':n_features, 'Height':height, 'Width':width, 'Drop':droprate, 'LR':lr, 'Blocks':num_blocks, 'R':r, 'Weighted':weighted, 'Transform':transform, 'Intensity':intensity, 'intensity type':intensity_type, 'Seed':seed}, {'hparam/Barley':Barley_Acc, 'hparam/Broken':Broken_Acc, 'hparam/Oat_Acc':Oat_Acc, 'hparam/Rye':Rye_Acc, 'hparam/Wheat':Wheat_Acc, 'hparam/Train_Accuracy':train_acc, 'hparam/Test_Accuracy':test_acc})
    
    #save model
    torch.save(model.state_dict(), '../Models/{date}_{model_choice}_Features={features}_Blocks={blocks}_Height={height}_Width={width}'.format(date=datetime.today().strftime('%d-%m-%y:%H%M'), model_choice=model_choice, blocks=num_blocks, features=n_features, height=height, width=width))
