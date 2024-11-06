#!/bin/bash

# Changing directory to build inside the application folders
cd ..

delete_manifests() {
    service_folder=$1
    cd $service_folder/
    echo $PWD # Check Directory
    kubectl delete -f kubernetes/
    cd ../
}

apply_manifests() {
    service_folder=$1
    cd $service_folder/
    echo $PWD # Check Directory
    kubectl apply -f kubernetes/
    cd ../
}

# delete_manifests '00-otel-collector'
# delete_manifests '02-user-service'
delete_manifests '03-product-service'
# apply_manifests '00-otel-collector'
# apply_manifests '02-user-service'
apply_manifests '03-product-service'



sleep 2.5
echo -ne '##                            (15%)\r'
sleep 2.5
echo -ne '#####                         (25%)\r'
sleep 3.5
echo -ne '#############                 (50%)\r'
sleep 5.3
echo -ne '#####################         (75%)\r'
sleep 5.3
echo -ne '############################# (100%)\r'
echo -ne '\n'