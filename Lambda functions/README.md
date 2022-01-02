# Instructions to deploy Lambda functions

Each folder in this directory contains a separate Lambda function configuration. Each Lambda function can have the following configuration parameters
1.  Lambda Layer 
2.  Invocation Trigger
3.  Environment variables

Below are common steps needed to be followed to deploy a lambda function which has all three requirements. Do note that, some lambda functions don't have any of the three, so deploying them should be straight forward.

We will take '**eagleview_image_metadata_filter**' as an example.
### Lambda Code
1.  Create a new lambda function with Python3.7 runtime and select the created role as detailed in the [deployment-document](../docs/deployment.md) lambda function section.
2.  Copy the contents of [eagleview_image_metadata_filter/lambda_function.py](./eagleview_image_metadata_filter/lambda_function.py) into the new lambda function.
3.  Right click on folder directory on the left side and select 'New file' and name it **coordinate_grid.py**
4.  Copy the contents of [eagleview_image_metadata_filter/coordinate_grid.py](./eagleview_image_metadata_filter/coordinate_grid.py) into the new file.
5.  Right click on folder directory on the left side and select 'New file' and name it **metadata_filter_helper.py**
6.  Copy the contents of [eagleview_image_metadata_filter/metadata_filter_helper.py](./eagleview_image_metadata_filter/metadata_filter_helper.py) into the new file.
### Invocation Trigger
7.  Click on **Add Trigger** on the top navigation bar and select '**SNS**' and then select the topic '**trigger_ev_process**'
### Environment Variables
8.  Click on **Configuration** --> **Environment Variables**
9.  Add the following key-value pairs to environment variables (Note, if you changed these S3 bucket names, you need to use the ones you created)
    - UnprocessedBucket : eagleview-unprocessed-images
### Lambda Layer
10. Click on **Code** and Scroll all the way down and click on **Add a layer**
11. Click on **Custom Layers** and select **geopandas** and the latest version. (You should have created this layer before adding it, follow the steps in the [deployment-document](../docs/deployment.md))

That's it, deploy all functions in the similar fashion, turn on your rekognition model and you should have the application running.

Tutorial attached below ->
![Lambda-Example](../images/lambda-example.gif)